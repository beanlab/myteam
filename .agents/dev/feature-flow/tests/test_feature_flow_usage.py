from __future__ import annotations

import importlib.util
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
