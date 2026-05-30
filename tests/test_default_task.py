from __future__ import annotations

from pathlib import Path

from myteam.disclosure import TaskStepSettings
from myteam.tasks.definition.default_task import run_default_task
from myteam.tasks.definition.models import StepResult


def test_run_default_task_uses_prompt_only_without_task_settings(tmp_path: Path, monkeypatch):
    seen: dict[str, object] = {}
    prompt = "workflow prompt"

    class FakeAgentContext:
        def __init__(self, **kwargs):
            seen["context_kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def run_agent(self, **kwargs):
            seen["run_agent_kwargs"] = kwargs
            return StepResult(status="completed")

    monkeypatch.setattr("myteam.tasks.definition.default_task.AgentContext", FakeAgentContext)

    result = run_default_task(prompt, cwd=tmp_path)

    assert result.status == "completed"
    assert seen["context_kwargs"] == {
        "cwd": tmp_path,
        "usage_logging": None,
        "timeout": None,
    }
    assert isinstance(seen["run_agent_kwargs"]["prompt"], str)
    assert seen["run_agent_kwargs"]["prompt"]


def test_run_default_task_forwards_task_settings(tmp_path: Path, monkeypatch):
    seen: dict[str, object] = {}
    prompt = "workflow prompt"
    task_settings = TaskStepSettings(
        agent="codex",
        model="gpt-5.4-mini",
        input={"topic": "release"},
        output={"summary": "short summary"},
        interactive=False,
        session_id="session-123",
        fork=False,
        extra_args=("--sandbox", "workspace-write"),
        usage_logging="verbose",
        timeout=77,
    )

    class FakeAgentContext:
        def __init__(self, **kwargs):
            seen["context_kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def run_agent(self, **kwargs):
            seen["run_agent_kwargs"] = kwargs
            return StepResult(status="completed")

    monkeypatch.setattr("myteam.tasks.definition.default_task.AgentContext", FakeAgentContext)

    result = run_default_task(
        prompt,
        cwd=tmp_path,
        task_settings=task_settings,
    )

    assert result.status == "completed"
    assert seen["context_kwargs"] == {
        "cwd": tmp_path,
        "usage_logging": "verbose",
        "timeout": 77,
    }
    assert seen["run_agent_kwargs"]["prompt"]
    assert seen["run_agent_kwargs"]["agent"] == "codex"
    assert seen["run_agent_kwargs"]["model"] == "gpt-5.4-mini"
    assert seen["run_agent_kwargs"]["input"] == {"topic": "release"}
    assert seen["run_agent_kwargs"]["output"] == {"summary": "short summary"}
    assert seen["run_agent_kwargs"]["interactive"] is False
    assert seen["run_agent_kwargs"]["session_id"] == "session-123"
    assert seen["run_agent_kwargs"]["fork"] is False
    assert seen["run_agent_kwargs"]["extra_args"] == ("--sandbox", "workspace-write")
