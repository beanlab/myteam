from __future__ import annotations

from typing import Any

import pytest

from myteam.workflow.engine import run_workflow
from myteam.workflow.models import StepResult


def test_run_workflow_executes_steps_in_authored_order(monkeypatch):
    calls: list[str] = []

    def fake_execute_step(step_definition: dict[str, Any]) -> StepResult:
        calls.append(step_definition["prompt"])
        return StepResult(
            status="completed",
            output={"value": step_definition["output"]["value"]},
            agent_name=step_definition["agent"],
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

    assert calls == ["one", "two"]
    assert result.status == "completed"
    assert result.output is not None
    assert list(result.output) == ["first", "second"]


def test_run_workflow_stops_at_first_failed_step(monkeypatch):
    calls: list[str] = []

    def fake_execute_step(step_definition: dict[str, Any]) -> StepResult:
        calls.append(step_definition["prompt"])
        if step_definition["prompt"] == "two":
            return StepResult(
                status="failed",
                error_type="completion_missing",
                error_message="missing completion",
            )
        return StepResult(
            status="completed",
            output={"value": step_definition["output"]["value"]},
            agent_name=step_definition["agent"],
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

    assert calls == ["one", "two"]
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
    seen_step_definitions: list[dict[str, Any]] = []

    def fake_execute_step(step_definition: dict[str, Any]) -> StepResult:
        seen_step_definitions.append(step_definition)
        if step_definition["prompt"] == "Write a draft.":
            return StepResult(
                status="completed",
                output={"title": "Draft Title"},
                agent_name=step_definition["agent"],
            )
        return StepResult(
            status="completed",
            output={"reviewed_title": "Reviewed Draft Title"},
            resolved_input={"title": "Draft Title"},
            agent_name=step_definition["agent"],
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

    assert len(seen_step_definitions) == 2
    assert seen_step_definitions[0] == {
        "prompt": "Write a draft.",
        "output": {"title": "draft title"},
        "input": None,
        "agent": "codex",
    }
    assert seen_step_definitions[1] == {
        "input": {"title": "Draft Title"},
        "prompt": "Review the draft.",
        "output": {"reviewed_title": "reviewed title"},
        "agent": "codex",
    }
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


def test_run_workflow_injects_default_agent_before_execution(monkeypatch):
    seen_step_definition: dict[str, Any] = {}

    def fake_execute_step(step_definition: dict[str, Any]) -> StepResult:
        seen_step_definition.update(step_definition)
        return StepResult(
            status="completed",
            output={"value": "draft"},
            agent_name=step_definition["agent"],
        )

    monkeypatch.setattr("myteam.workflow.engine.execute_step", fake_execute_step)

    result = run_workflow(
        {
            "draft": {
                "prompt": "Write a draft.",
                "output": {"value": "draft"},
            }
        }
    )

    assert result.status == "completed"
    assert seen_step_definition["agent"] == "codex"


def test_run_workflow_rejects_completed_step_without_agent_name(monkeypatch):
    def fake_execute_step(step_definition: dict[str, Any]) -> StepResult:
        return StepResult(
            status="completed",
            output={"value": step_definition["prompt"]},
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
    def fake_execute_step(step_definition: dict[str, Any]) -> StepResult:
        if step_definition["prompt"] == "Write a draft.":
            return StepResult(
                status="completed",
                output={"title": "Draft Title"},
                resolved_input=None,
                agent_name=step_definition["agent"],
            )
        return StepResult(
            status="completed",
            output={"reviewed_title": "Reviewed Draft Title"},
            resolved_input=None,
            agent_name=step_definition["agent"],
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
