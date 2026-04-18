from __future__ import annotations

from myteam.workflow.engine import run_workflow
from myteam.workflow.models import StepResult


def test_run_workflow_returns_completed_output_mapping(monkeypatch):
    def fake_execute_step(step_name, step, run_context):
        if step_name == "draft":
            assert run_context.prior_steps == {}
            return StepResult(
                step_name=step_name,
                status="completed",
                input=None,
                agent="codex",
                output={"title": "Draft"},
            )

        assert run_context.prior_steps == {
            "draft": {
                "prompt": "Write the draft.",
                "input": None,
                "agent": "codex",
                "output": {"title": "Draft"},
            }
        }
        return StepResult(
            step_name=step_name,
            status="completed",
            input={"draft": {"title": "Draft"}},
            agent="codex",
            output={"winner": "Draft"},
        )

    monkeypatch.setattr("myteam.workflow.engine.execute_step", fake_execute_step)

    result = run_workflow(
        {
            "draft": {
                "prompt": "Write the draft.",
                "output": {"title": "Draft title"},
            },
            "review": {
                "prompt": "Review the draft.",
                "output": {"winner": "Winning title"},
            },
        }
    )

    assert result.status == "completed"
    assert result.failed_step_name is None
    assert result.output == {
        "draft": {
            "prompt": "Write the draft.",
            "input": None,
            "agent": "codex",
            "output": {"title": "Draft"},
        },
        "review": {
            "prompt": "Review the draft.",
            "input": {"draft": {"title": "Draft"}},
            "agent": "codex",
            "output": {"winner": "Draft"},
        },
    }


def test_run_workflow_stops_after_first_failed_step(monkeypatch):
    seen_steps = []

    def fake_execute_step(step_name, step, run_context):
        del step, run_context
        seen_steps.append(step_name)
        if step_name == "draft":
            return StepResult(
                step_name=step_name,
                status="completed",
                input=None,
                agent="codex",
                output={"title": "Draft"},
            )
        return StepResult(
            step_name=step_name,
            status="failed",
            error_type="step_execution_error",
            error_message="boom",
        )

    monkeypatch.setattr("myteam.workflow.engine.execute_step", fake_execute_step)

    result = run_workflow(
        {
            "draft": {
                "prompt": "Write the draft.",
                "output": {"title": "Draft title"},
            },
            "review": {
                "prompt": "Review the draft.",
                "output": {"winner": "Winning title"},
            },
            "publish": {
                "prompt": "Publish the result.",
                "output": {"published": "yes"},
            },
        }
    )

    assert seen_steps == ["draft", "review"]
    assert result.status == "failed"
    assert result.failed_step_name == "review"
    assert result.output == {
        "draft": {
            "prompt": "Write the draft.",
            "input": None,
            "agent": "codex",
            "output": {"title": "Draft"},
        }
    }
