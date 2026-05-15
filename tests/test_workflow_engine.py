from __future__ import annotations

from typing import Any

import pytest

from myteam.workflow.engine import run_workflow
from myteam.workflow.models import StepResult


def test_run_workflow_executes_steps_in_authored_order(monkeypatch):
    calls: list[str] = []

    def fake_run_agent(
        *,
        prompt: str,
        output: dict[str, Any],
        input: Any,
        agent: str,
        model: str | None,
        extra_args: list[str] | None,
    ) -> StepResult:
        calls.append(prompt)
        return StepResult(
            status="completed",
            output={"value": output["value"]},
            agent_name=agent,
        )

    monkeypatch.setattr("myteam.workflow.engine.run_agent", fake_run_agent)

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

    def fake_run_agent(
        *,
        prompt: str,
        output: dict[str, Any],
        input: Any,
        agent: str,
        model: str | None,
        extra_args: list[str] | None,
    ) -> StepResult:
        calls.append(prompt)
        if prompt == "two":
            return StepResult(
                status="failed",
                error_type="completion_missing",
                error_message="missing completion",
            )
        return StepResult(
            status="completed",
            output={"value": output["value"]},
            agent_name=agent,
        )

    monkeypatch.setattr("myteam.workflow.engine.run_agent", fake_run_agent)

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

    def fake_run_agent(
        *,
        prompt: str,
        output: dict[str, Any],
        input: Any,
        agent: str,
        model: str | None,
        extra_args: list[str] | None,
    ) -> StepResult:
        seen_step_definitions.append(
            {
                "agent": agent,
                "input": input,
                "output": output,
                "prompt": prompt,
            }
        )
        if prompt == "Write a draft.":
            return StepResult(
                status="completed",
                output={"title": "Draft Title"},
                agent_name=agent,
            )
        return StepResult(
            status="completed",
            output={"reviewed_title": "Reviewed Draft Title"},
            resolved_input={"title": "Draft Title"},
            agent_name=agent,
        )

    monkeypatch.setattr("myteam.workflow.engine.run_agent", fake_run_agent)

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

    def fake_run_agent(
        *,
        prompt: str,
        output: dict[str, Any],
        input: Any,
        agent: str,
        model: str | None,
        extra_args: list[str] | None,
    ) -> StepResult:
        seen_step_definition.update(
            {
                "agent": agent,
                "input": input,
                "output": output,
                "prompt": prompt,
            }
        )
        return StepResult(
            status="completed",
            output={"value": "draft"},
            agent_name=agent,
        )

    monkeypatch.setattr("myteam.workflow.engine.run_agent", fake_run_agent)

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


def test_run_workflow_passes_model_and_extra_args_to_agent(monkeypatch):
    seen_step_definition: dict[str, Any] = {}

    def fake_run_agent(
        *,
        prompt: str,
        output: dict[str, Any],
        input: Any,
        agent: str,
        model: str | None,
        extra_args: list[str] | None,
    ) -> StepResult:
        seen_step_definition.update(
            {
                "agent": agent,
                "extra_args": extra_args,
                "input": input,
                "model": model,
                "output": output,
                "prompt": prompt,
            }
        )
        return StepResult(
            status="completed",
            output={"value": "draft"},
            agent_name=agent,
        )

    monkeypatch.setattr("myteam.workflow.engine.run_agent", fake_run_agent)

    result = run_workflow(
        {
            "draft": {
                "prompt": "Write a draft.",
                "model": "gpt-5.4",
                "extra_args": ["--exec", "pytest -q"],
                "output": {"value": "draft"},
            }
        }
    )

    assert result.status == "completed"
    assert seen_step_definition["model"] == "gpt-5.4"
    assert seen_step_definition["extra_args"] == ["--exec", "pytest -q"]


def test_run_workflow_rejects_completed_step_without_agent_name(monkeypatch):
    def fake_run_agent(
        *,
        prompt: str,
        output: dict[str, Any],
        input: Any,
        agent: str,
        model: str | None,
        extra_args: list[str] | None,
    ) -> StepResult:
        return StepResult(
            status="completed",
            output={"value": prompt},
        )

    monkeypatch.setattr("myteam.workflow.engine.run_agent", fake_run_agent)

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
    def fake_run_agent(
        *,
        prompt: str,
        output: dict[str, Any],
        input: Any,
        agent: str,
        model: str | None,
        extra_args: list[str] | None,
    ) -> StepResult:
        if prompt == "Write a draft.":
            return StepResult(
                status="completed",
                output={"title": "Draft Title"},
                resolved_input=None,
                agent_name=agent,
            )
        return StepResult(
            status="completed",
            output={"reviewed_title": "Reviewed Draft Title"},
            resolved_input=None,
            agent_name=agent,
        )

    monkeypatch.setattr("myteam.workflow.engine.run_agent", fake_run_agent)

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
