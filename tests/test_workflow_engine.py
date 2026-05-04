from __future__ import annotations

from typing import Any

import pytest

from myteam.workflow.engine import run_workflow
from myteam.workflow.models import StepResult


def test_run_workflow_executes_steps_in_authored_order(monkeypatch):
    calls: list[str] = []

    def fake_execute_step(
        step_name: str,
        step_definition: dict[str, Any],
        *,
        prior_steps,
        default_agent: str,
        inactivity_timeout_seconds: int,
        graceful_shutdown_timeout_seconds: int,
    ) -> StepResult:
        calls.append(step_name)
        return StepResult(
            step_name=step_name,
            status="completed",
            output={"value": step_name},
            agent_name=default_agent,
        )

    monkeypatch.setattr("myteam.workflow.engine.execute_step", fake_execute_step)

    result = run_workflow(
        {
            "first": {
                "prompt": "one",
                "output": {"value": "first"},
            },
            "second": {
                "prompt": "two",
                "output": {"value": "second"},
            },
        }
    )

    assert calls == ["first", "second"]
    assert result.status == "completed"
    assert result.output is not None
    assert list(result.output) == ["first", "second"]


def test_run_workflow_stops_at_first_failed_step(monkeypatch):
    calls: list[str] = []

    def fake_execute_step(
        step_name: str,
        step_definition: dict[str, Any],
        *,
        prior_steps,
        default_agent: str,
        inactivity_timeout_seconds: int,
        graceful_shutdown_timeout_seconds: int,
    ) -> StepResult:
        calls.append(step_name)
        if step_name == "second":
            return StepResult(
                step_name=step_name,
                status="failed",
                error_type="completion_missing",
                error_message="missing completion",
            )
        return StepResult(
            step_name=step_name,
            status="completed",
            output={"value": step_name},
            agent_name=default_agent,
        )

    monkeypatch.setattr("myteam.workflow.engine.execute_step", fake_execute_step)

    result = run_workflow(
        {
            "first": {
                "prompt": "one",
                "output": {"value": "first"},
            },
            "second": {
                "prompt": "two",
                "output": {"value": "second"},
            },
            "third": {
                "prompt": "three",
                "output": {"value": "third"},
            },
        }
    )

    assert calls == ["first", "second"]
    assert result.status == "failed"
    assert result.failed_step_name == "second"
    assert result.error_message == "missing completion"
    assert result.output == {
        "first": {
            "prompt": "one",
            "input": None,
            "agent": "codex",
            "output": {"value": "first"},
        }
    }


def test_run_workflow_stores_completed_step_state_for_later_references(monkeypatch):
    seen_prior_steps: list[dict[str, Any]] = []

    def fake_execute_step(
        step_name: str,
        step_definition: dict[str, Any],
        *,
        prior_steps,
        default_agent: str,
        inactivity_timeout_seconds: int,
        graceful_shutdown_timeout_seconds: int,
    ) -> StepResult:
        seen_prior_steps.append(dict(prior_steps))
        if step_name == "draft":
            return StepResult(
                step_name=step_name,
                status="completed",
                output={"title": "Draft Title"},
                agent_name=default_agent,
            )
        return StepResult(
            step_name=step_name,
            status="completed",
            output={"reviewed_title": "Reviewed Draft Title"},
            resolved_input={"title": "Draft Title"},
            agent_name=default_agent,
        )

    monkeypatch.setattr("myteam.workflow.engine.execute_step", fake_execute_step)

    result = run_workflow(
        {
            "draft": {
                "prompt": "Write a draft.",
                "output": {
                    "title": "draft title",
                },
            },
            "review": {
                "input": {
                    "title": "$draft.output.title",
                },
                "prompt": "Review the draft.",
                "output": {
                    "reviewed_title": "reviewed title",
                },
            },
        }
    )

    assert seen_prior_steps == [
        {},
        {
            "draft": {
                "prompt": "Write a draft.",
                "input": None,
                "agent": "codex",
                "output": {"title": "Draft Title"},
            }
        },
    ]
    assert result.status == "completed"
    assert result.output == {
        "draft": {
            "prompt": "Write a draft.",
            "input": None,
            "agent": "codex",
            "output": {"title": "Draft Title"},
        },
        "review": {
            "prompt": "Review the draft.",
            "input": {"title": "Draft Title"},
            "agent": "codex",
            "output": {"reviewed_title": "Reviewed Draft Title"},
        },
    }


def test_run_workflow_passes_runtime_settings_through_to_executor(monkeypatch):
    seen: dict[str, Any] = {}

    def fake_execute_step(
        step_name: str,
        step_definition: dict[str, Any],
        *,
        prior_steps,
        default_agent: str,
        inactivity_timeout_seconds: int,
        graceful_shutdown_timeout_seconds: int,
    ) -> StepResult:
        seen["default_agent"] = default_agent
        seen["inactivity_timeout_seconds"] = inactivity_timeout_seconds
        seen["graceful_shutdown_timeout_seconds"] = graceful_shutdown_timeout_seconds
        return StepResult(
            step_name=step_name,
            status="completed",
            output={"value": step_name},
            agent_name=default_agent,
        )

    monkeypatch.setattr("myteam.workflow.engine.execute_step", fake_execute_step)

    result = run_workflow(
        {
            "draft": {
                "prompt": "Write a draft.",
                "output": {"value": "draft"},
            }
        },
        default_agent="test-agent",
        inactivity_timeout_seconds=12,
        graceful_shutdown_timeout_seconds=7,
    )

    assert result.status == "completed"
    assert seen == {
        "default_agent": "test-agent",
        "inactivity_timeout_seconds": 12,
        "graceful_shutdown_timeout_seconds": 7,
    }


def test_run_workflow_rejects_completed_step_without_agent_name(monkeypatch):
    def fake_execute_step(
        step_name: str,
        step_definition: dict[str, Any],
        *,
        prior_steps,
        default_agent: str,
        inactivity_timeout_seconds: int,
        graceful_shutdown_timeout_seconds: int,
    ) -> StepResult:
        return StepResult(
            step_name=step_name,
            status="completed",
            output={"value": step_name},
        )

    monkeypatch.setattr("myteam.workflow.engine.execute_step", fake_execute_step)

    with pytest.raises(ValueError, match="missing agent_name"):
        run_workflow(
            {
                "draft": {
                    "prompt": "Write a draft.",
                    "input": None,
                    "output": {"value": "draft"},
                }
            }
        )


def test_run_workflow_stores_null_input_for_completed_steps(monkeypatch):
    def fake_execute_step(
        step_name: str,
        step_definition: dict[str, Any],
        *,
        prior_steps,
        default_agent: str,
        inactivity_timeout_seconds: int,
        graceful_shutdown_timeout_seconds: int,
    ) -> StepResult:
        if step_name == "draft":
            return StepResult(
                step_name=step_name,
                status="completed",
                output={"title": "Draft Title"},
                resolved_input=None,
                agent_name=default_agent,
            )
        return StepResult(
            step_name=step_name,
            status="completed",
            output={"reviewed_title": "Reviewed Draft Title"},
            resolved_input=None,
            agent_name=default_agent,
        )

    monkeypatch.setattr("myteam.workflow.engine.execute_step", fake_execute_step)

    result = run_workflow(
        {
            "draft": {
                "prompt": "Write a draft.",
                "input": None,
                "output": {
                    "title": "draft title",
                },
            },
            "review": {
                "input": None,
                "prompt": "Review the draft.",
                "output": {
                    "reviewed_title": "reviewed title",
                },
            },
        }
    )

    assert result.status == "completed"
    assert result.output == {
        "draft": {
            "prompt": "Write a draft.",
            "input": None,
            "agent": "codex",
            "output": {"title": "Draft Title"},
        },
        "review": {
            "prompt": "Review the draft.",
            "input": None,
            "agent": "codex",
            "output": {"reviewed_title": "Reviewed Draft Title"},
        },
    }

