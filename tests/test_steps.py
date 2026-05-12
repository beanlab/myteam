from __future__ import annotations

from typing import Any

from myteam.workflow.steps import run_agent
from myteam.workflow.terminal.session import TerminalSessionResult


def test_run_agent_returns_completed_result(monkeypatch):
    seen: dict[str, Any] = {}

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        seen["argv"] = argv
        seen["exit_input"] = exit_input
        seen["inactivity_timeout_seconds"] = inactivity_timeout_seconds
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    monkeypatch.setattr("myteam.workflow.steps.run_terminal_session", fake_run_terminal_session)

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
    assert "printenv CODEX_THREAD_ID" in seen["argv"][1]
    assert b"/quit" in seen["exit_input"]


def test_run_agent_reports_missing_result(monkeypatch):
    def fake_run_terminal_session(*_args, **_kwargs) -> TerminalSessionResult:
        return TerminalSessionResult(exit_code=0, transcript="runner transcript", payload=None)

    monkeypatch.setattr("myteam.workflow.steps.run_terminal_session", fake_run_terminal_session)

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
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        seen["argv"] = argv
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    monkeypatch.setattr("myteam.workflow.steps.run_terminal_session", fake_run_terminal_session)

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
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        seen["argv"] = argv
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done", "session_id": "thread-123"},
        )

    monkeypatch.setattr("myteam.workflow.steps.run_terminal_session", fake_run_terminal_session)

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
