from __future__ import annotations

from pathlib import Path

from myteam.workflow.models import StepResult
from myteam.workflow.default_workflow import (
    DEFAULT_AGENT,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_USAGE_LOGGING,
    load_default_workflow_config,
    run_default_workflow,
)


def test_load_default_workflow_config_uses_defaults_when_file_missing(tmp_path: Path):
    config = load_default_workflow_config(
        tmp_path,
        default_agent=DEFAULT_AGENT,
        default_model=DEFAULT_MODEL,
        default_usage_logging=DEFAULT_USAGE_LOGGING,
        default_timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    )

    assert config.agent == DEFAULT_AGENT
    assert config.model == DEFAULT_MODEL
    assert config.usage_logging == DEFAULT_USAGE_LOGGING
    assert config.inactivity_timeout_seconds == DEFAULT_TIMEOUT_SECONDS


def test_load_default_workflow_config_prefers_nested_section(tmp_path: Path):
    (tmp_path / ".config.yaml").write_text(
        "default_workflow:\n"
        "  agent: pi\n"
        "  model: gpt-5.5\n"
        "  usage_logging: verbose\n"
        "  inactivity_timeout_seconds: 1200\n",
        encoding="utf-8",
    )

    config = load_default_workflow_config(
        tmp_path,
        default_agent=DEFAULT_AGENT,
        default_model=DEFAULT_MODEL,
        default_usage_logging=DEFAULT_USAGE_LOGGING,
        default_timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    )

    assert config.agent == "pi"
    assert config.model == "gpt-5.5"
    assert config.usage_logging == "verbose"
    assert config.inactivity_timeout_seconds == 1200


def test_load_default_workflow_config_accepts_top_level_keys(tmp_path: Path):
    (tmp_path / ".config.yaml").write_text(
        "agent: codex_mini\n"
        "timeout: 45\n",
        encoding="utf-8",
    )

    config = load_default_workflow_config(
        tmp_path,
        default_agent=DEFAULT_AGENT,
        default_model=DEFAULT_MODEL,
        default_usage_logging=DEFAULT_USAGE_LOGGING,
        default_timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    )

    assert config.agent == "codex_mini"
    assert config.model == DEFAULT_MODEL
    assert config.usage_logging == DEFAULT_USAGE_LOGGING
    assert config.inactivity_timeout_seconds == 45


def test_load_default_workflow_config_finds_config_under_project_root(tmp_path: Path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    local_root = project_root / ".myteam"
    local_root.mkdir()
    (local_root / ".config.yaml").write_text(
        "default_workflow:\n"
        "  agent: pi\n"
        "  model: gpt-5.5\n",
        encoding="utf-8",
    )

    config = load_default_workflow_config(
        project_root,
        default_agent=DEFAULT_AGENT,
        default_model=DEFAULT_MODEL,
        default_usage_logging=DEFAULT_USAGE_LOGGING,
        default_timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    )

    assert config.agent == "pi"
    assert config.model == "gpt-5.5"


def test_run_default_workflow_uses_config_file_values(tmp_path: Path, monkeypatch):
    (tmp_path / ".config.yaml").write_text(
        "default_workflow:\n"
        "  agent: pi\n"
        "  model: gpt-5.5\n"
        "  usage_logging: none\n"
        "  timeout_seconds: 321\n",
        encoding="utf-8",
    )

    seen: dict[str, object] = {}

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

    monkeypatch.setattr("myteam.workflow.default_workflow.AgentContext", FakeAgentContext)

    result = run_default_workflow("Say 'Ready'", cwd=tmp_path)

    assert result.status == "completed"
    assert seen["context_kwargs"] == {
        "cwd": tmp_path,
        "usage_logging": None,
        "inactivity_timeout_seconds": None,
    }
    assert seen["run_agent_kwargs"] == {"prompt": "Say 'Ready'"}


def test_run_default_workflow_explicit_arguments_override_config(tmp_path: Path, monkeypatch):
    (tmp_path / ".config.yaml").write_text(
        "default_workflow:\n"
        "  agent: pi\n"
        "  model: gpt-5.5\n",
        encoding="utf-8",
    )

    seen: dict[str, object] = {}

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

    monkeypatch.setattr("myteam.workflow.default_workflow.AgentContext", FakeAgentContext)

    result = run_default_workflow(
        "Say 'Ready'",
        cwd=tmp_path,
        agent="codex",
        model="gpt-5.4-mini",
        usage_logging="verbose",
        inactivity_timeout_seconds=77,
    )

    assert result.status == "completed"
    assert seen["context_kwargs"] == {
        "cwd": tmp_path,
        "usage_logging": "verbose",
        "inactivity_timeout_seconds": 77,
    }
    assert seen["run_agent_kwargs"]["agent"] == "codex"
    assert seen["run_agent_kwargs"]["model"] == "gpt-5.4-mini"
