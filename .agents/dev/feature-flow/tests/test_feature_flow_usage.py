from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from myteam import SessionResult, UsageInfo


FEATURE_FLOW_PATH = Path(".agents/dev/feature-flow/feature_flow.py")


def load_feature_flow() -> ModuleType:
    spec = importlib.util.spec_from_file_location("feature_flow_under_test", FEATURE_FLOW_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def session_result(output: dict[str, Any] | None, total_tokens: int) -> SessionResult:
    return SessionResult(
        exit_code=0,
        output=output,
        usage=[
            UsageInfo(
                model="model-a",
                input_tokens=total_tokens - 20,
                cached_input_tokens=10,
                output_tokens=20,
                reasoning_output_tokens=5,
                total_tokens=total_tokens,
                estimated_cost=total_tokens / 100,
            )
        ],
        transcript="",
        session_id="native-session",
    )


def test_feature_flow_reports_cumulative_snapshots_and_step_deltas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature_flow = load_feature_flow()
    results = iter((session_result({"result": "first"}, 100), session_result({"result": "second"}, 150)))
    monkeypatch.setattr(feature_flow, "run_agent", lambda **_: next(results))
    state = feature_flow.FlowState()

    feature_flow.run_step(state, "01-discover.md.jinja", output={"result": "value"})
    feature_flow.run_step(
        state,
        "10-sign-off.md.jinja",
        output={"result": "value"},
        session_id="native-session",
    )

    report = feature_flow.build_usage_report(state)

    assert [snapshot["session_mode"] for snapshot in report["snapshots"]] == ["new", "resumed"]
    assert all(snapshot["native_session_id"] == "native-session" for snapshot in report["snapshots"])
    assert report["sessions"][0]["usage"][0]["total_tokens"] == 150
    usage_by_step = {step["step"]: step["usage"][0] for step in report["steps"]}
    assert usage_by_step["01-discover"]["total_tokens"] == 100
    assert usage_by_step["10-sign-off"]["total_tokens"] == 50
    assert report["totals"]["total_tokens"] == 150
    assert report["totals"]["estimated_cost"] == pytest.approx(1.5)


def test_feature_flow_records_usage_before_stopping_on_no_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature_flow = load_feature_flow()
    monkeypatch.setattr(
        feature_flow,
        "run_agent",
        lambda **_: session_result(None, 100),
    )
    state = feature_flow.FlowState()

    with pytest.raises(feature_flow.WorkflowStopped):
        feature_flow.run_step(state, "01-discover.md.jinja", output={"result": "value"})

    assert len(state.usage_snapshots) == 1
    assert state.usage_snapshots[0].outcome == "no_result"
    assert state.usage_snapshots[0].native_session_id == "native-session"


def test_failed_final_verification_returns_to_implementation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature_flow = load_feature_flow()
    state = feature_flow.FlowState()
    failure = {"passed": False, "commands_run": ["uv run pytest"], "results": "failed"}
    monkeypatch.setattr(
        feature_flow,
        "run_step",
        lambda *_, **__: session_result(failure, 100),
    )

    with pytest.raises(feature_flow.ReturnToImplementation) as raised:
        feature_flow.run_final_verification(state)

    assert raised.value.feedback == failure
    assert raised.value.source == "final_verification"


def test_wrap_up_routes_requested_changes_to_the_owning_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature_flow = load_feature_flow()
    state = feature_flow.FlowState()
    requested_change = {
        "decision": "changes_requested",
        "return_to": "documentation",
        "requested_changes": "Clarify the user guide.",
    }
    monkeypatch.setattr(
        feature_flow,
        "run_step",
        lambda *_, **__: session_result(requested_change, 100),
    )

    with pytest.raises(feature_flow.ReturnToDocumentation) as raised:
        feature_flow.run_wrap_up(state)

    assert raised.value.feedback == requested_change
    assert raised.value.source == "wrap_up"


def test_main_writes_full_run_artifact_and_reports_concise_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    feature_flow = load_feature_flow()
    artifact_directory = tmp_path / "runs"
    reported: list[str] = []
    monkeypatch.setattr(feature_flow, "RUN_ARTIFACT_DIRECTORY", artifact_directory)
    monkeypatch.setattr(feature_flow, "current_branch_name", lambda: "feature/my change")
    monkeypatch.setattr(
        feature_flow,
        "run_discovery",
        lambda _: {
            "status": "complete",
            "feature_brief": {"desired_behavior": "example"},
            "wrap_up": {"pull_request_url": "https://example.test/pull/1"},
        },
    )
    monkeypatch.setattr(feature_flow, "report_workflow_result", reported.append)

    feature_flow.main()

    artifacts = list(artifact_directory.glob("*-feature-flow-feature-my-change.json"))
    assert len(artifacts) == 1
    artifact = json.loads(artifacts[0].read_text())
    assert artifact["feature_brief"] == {"desired_behavior": "example"}
    assert "usage" in artifact
    assert json.loads(reported[0]) == {
        "total_cost": 0.0,
        "pull_request_url": "https://example.test/pull/1",
        "report_path": str(artifacts[0]),
    }
