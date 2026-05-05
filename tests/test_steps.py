from __future__ import annotations

from typing import Any

from myteam.workflow.steps import execute_step
from myteam.workflow.terminal.session import TerminalSessionResult


def test_execute_step_returns_completed_result(monkeypatch):
    seen: dict[str, Any] = {}

    def fake_run_terminal_session(
        argv: list[str],
        *,
        initial_input: bytes,
        exit_input: bytes,
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        seen["argv"] = argv
        seen["initial_input"] = initial_input.decode("utf-8", errors="replace")
        seen["exit_input"] = exit_input
        seen["inactivity_timeout_seconds"] = inactivity_timeout_seconds
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    monkeypatch.setattr("myteam.workflow.steps.run_terminal_session", fake_run_terminal_session)

    result = execute_step(
        {
            "agent": "codex",
            "prompt": "Write a summary.",
            "output": {"summary": "short summary"},
        }
    )

    assert result.status == "completed"
    assert result.output == {"summary": "done"}
    assert seen["argv"] == ["codex"]
    assert "workflow-result" in seen["initial_input"]
    assert b"/quit" in seen["exit_input"]


def test_execute_step_reports_missing_result(monkeypatch):
    def fake_run_terminal_session(*_args, **_kwargs) -> TerminalSessionResult:
        return TerminalSessionResult(exit_code=0, transcript="runner transcript", payload=None)

    monkeypatch.setattr("myteam.workflow.steps.run_terminal_session", fake_run_terminal_session)

    result = execute_step(
        {
            "agent": "codex",
            "prompt": "Write a summary.",
            "output": {"summary": "short summary"},
        }
    )

    assert result.status == "failed"
    assert result.error_type == "completion_missing"


def test_execute_step_requires_explicit_agent():
    result = execute_step(
        {
            "prompt": "Write a summary.",
            "output": {"summary": "short summary"},
        }
    )

    assert result.status == "failed"
    assert result.error_type == "agent_resolution"
    assert result.error_message == "Step definition is missing required field 'agent'."


def test_execute_step_preserves_literal_input(monkeypatch):
    seen: dict[str, Any] = {}

    def fake_run_terminal_session(
        argv: list[str],
        *,
        initial_input: bytes,
        exit_input: bytes,
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        seen["initial_input"] = initial_input.decode("utf-8", errors="replace")
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    monkeypatch.setattr("myteam.workflow.steps.run_terminal_session", fake_run_terminal_session)

    result = execute_step(
        {
            "agent": "codex",
            "input": {"topic": "release notes"},
            "prompt": "Write a summary.",
            "output": {"summary": "short summary"},
        }
    )

    assert result.status == "completed"
    assert result.resolved_input == {"topic": "release notes"}
    assert '"topic": "release notes"' in seen["initial_input"]
