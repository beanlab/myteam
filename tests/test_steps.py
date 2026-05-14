from __future__ import annotations

from typing import Any

from myteam.disclosure import PROJECT_ROOT_ENV_VAR
from myteam.workflow.agents.runtime import AgentRuntimeConfig
from myteam.workflow.steps import run_agent
from myteam.workflow.terminal.session import TerminalSessionResult


def fake_agent_config(*, session_id: str = "discovered-session") -> AgentRuntimeConfig:
    return AgentRuntimeConfig(
        name="codex",
        exec="codex",
        exit_sequence=b"/quit",
        encode_input=lambda text: text.encode("utf-8"),
        get_session_id=lambda nonce: session_id,
        build_argv=lambda prompt_text, current_session_id=None: (
            ["codex", "resume", current_session_id, prompt_text]
            if current_session_id is not None
            else ["codex", prompt_text]
        ),
        source="test",
    )


def test_run_agent_returns_completed_result(monkeypatch):
    seen: dict[str, Any] = {}

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        cwd,
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        seen["argv"] = argv
        seen["exit_input"] = exit_input
        seen["cwd"] = cwd
        seen["inactivity_timeout_seconds"] = inactivity_timeout_seconds
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    monkeypatch.setattr("myteam.workflow.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: fake_agent_config())

    result = run_agent(
        agent="codex",
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "completed"
    assert result.output == {"summary": "done"}
    assert seen["argv"][0] == "codex"
    assert len(seen["argv"]) == 2
    assert "workflow-result" in seen["argv"][1]
    assert "Session nonce:" in seen["argv"][1]
    assert b"/quit" in seen["exit_input"]
    assert seen["cwd"] is not None
    assert result.session_id == "discovered-session"


def test_run_agent_reports_missing_result(monkeypatch):
    def fake_run_terminal_session(*_args, **_kwargs) -> TerminalSessionResult:
        return TerminalSessionResult(exit_code=0, transcript="runner transcript", payload=None)

    monkeypatch.setattr("myteam.workflow.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: fake_agent_config())

    result = run_agent(
        agent="codex",
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "failed"
    assert result.error_type == "completion_missing"


def test_run_agent_requires_explicit_agent():
    result = run_agent(
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "failed"
    assert result.error_type == "agent_resolution"
    assert result.error_message == "Step definition is missing required field 'agent'."


def test_run_agent_preserves_literal_input(monkeypatch):
    seen: dict[str, Any] = {}

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        cwd,
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        seen["argv"] = argv
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    monkeypatch.setattr("myteam.workflow.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: fake_agent_config())

    result = run_agent(
        agent="codex",
        input={"topic": "release notes"},
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "completed"
    assert result.resolved_input == {"topic": "release notes"}
    assert '"topic": "release notes"' in seen["argv"][1]


def test_run_agent_resumes_session_and_preserves_session_id(monkeypatch):
    seen: dict[str, Any] = {}

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        cwd,
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        seen["argv"] = argv
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done", "session_id": "thread-123"},
        )

    monkeypatch.setattr("myteam.workflow.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: fake_agent_config())

    result = run_agent(
        agent="codex",
        session_id="thread-123",
        prompt="Write a summary.",
        output={"summary": "short summary", "session_id": "agent session ID"},
    )

    assert result.status == "completed"
    assert result.session_id == "thread-123"
    assert seen["argv"][0:3] == ["codex", "resume", "thread-123"]
    assert "workflow-result" in seen["argv"][3]


def test_run_agent_reports_session_discovery_failure(monkeypatch):
    def fake_run_terminal_session(*_args, **_kwargs) -> TerminalSessionResult:
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    def missing_session_id(_nonce: str) -> str:
        raise LookupError("No session found")

    config = fake_agent_config()
    config = AgentRuntimeConfig(
        name=config.name,
        exec=config.exec,
        exit_sequence=config.exit_sequence,
        encode_input=config.encode_input,
        get_session_id=missing_session_id,
        build_argv=config.build_argv,
        source=config.source,
    )
    monkeypatch.setattr("myteam.workflow.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: config)

    result = run_agent(
        agent="codex",
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "failed"
    assert result.error_type == "session_discovery"
    assert result.error_message == "No session found"


def test_run_agent_launches_from_project_root_when_called_under_active_root(tmp_path, monkeypatch):
    active_root = tmp_path / ".myteam"
    active_root.mkdir()
    monkeypatch.chdir(active_root)
    monkeypatch.setenv(PROJECT_ROOT_ENV_VAR, str(active_root))
    seen: dict[str, Any] = {}

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        cwd,
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        seen["cwd"] = cwd
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    def fake_resolve_agent_runtime_config(_agent, **kwargs):
        seen["project_root"] = kwargs["project_root"]
        return fake_agent_config()

    monkeypatch.setattr("myteam.workflow.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.steps.resolve_agent_runtime_config", fake_resolve_agent_runtime_config)

    result = run_agent(
        agent="codex",
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "completed"
    assert seen["cwd"] == tmp_path.resolve()
    assert seen["project_root"] == tmp_path.resolve()


def test_run_agent_allows_launch_cwd_override(tmp_path, monkeypatch):
    active_root = tmp_path / ".myteam"
    requested_cwd = tmp_path / "workspace"
    active_root.mkdir()
    requested_cwd.mkdir()
    monkeypatch.chdir(active_root)
    monkeypatch.setenv(PROJECT_ROOT_ENV_VAR, str(active_root))
    seen: dict[str, Any] = {}

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        cwd,
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        seen["cwd"] = cwd
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    def fake_resolve_agent_runtime_config(_agent, **kwargs):
        seen["project_root"] = kwargs["project_root"]
        return fake_agent_config()

    monkeypatch.setattr("myteam.workflow.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.steps.resolve_agent_runtime_config", fake_resolve_agent_runtime_config)

    result = run_agent(
        agent="codex",
        cwd=requested_cwd,
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "completed"
    assert seen["cwd"] == requested_cwd.resolve()
    assert seen["project_root"] == tmp_path.resolve()
