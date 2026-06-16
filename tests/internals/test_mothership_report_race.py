"""Implementation-level tests for workflow result race handling.

Result reports may arrive immediately before process exit. These tests exercise
the supervisor's storage path directly so race regressions fail with a focused
error instead of a flaky end-to-end timeout.
"""
from __future__ import annotations

import pytest

from myteam.workflows.execution.mothership import Mothership, RequestRecord
from myteam.workflows.execution.terminal import has_screen_rewriting_control


class FakeTerminal:
    def __init__(self) -> None:
        self.output = b""
        self.visual_state_restored = False
        self.cleared = False

    def write_stdout(self, data: bytes) -> None:
        self.output += data

    def clear(self) -> None:
        self.cleared = True

    def restore_visual_state(self) -> None:
        self.visual_state_restored = True


class FakeRecording:
    def snapshot(self) -> str:
        return "live transcript"


class FakeSession:
    session_id = "request-1"
    request_id = "request-1"
    recording = FakeRecording()

    def __init__(self, exit_code: int = 0) -> None:
        self.exit_code = exit_code

    def poll(self) -> int:
        return self.exit_code

    def wait(self, timeout=None) -> int:
        return self.exit_code

    def stderr_snapshot(self) -> str:
        return ""

    def close(self) -> None:
        pass


def test_workflow_result_is_stored_as_soon_as_rpc_is_accepted() -> None:
    mothership = Mothership()
    mothership.requests["request-1"] = RequestRecord(
        request_id="request-1",
        kind="workflow",
        status="running",
    )

    response = mothership._report_workflow_result(
        {
            "request_id": "request-1",
            "text": "first\n",
        }
    )
    mothership._report_workflow_result({"request_id": "request-1", "text": None})
    mothership._report_workflow_result({"request_id": "request-1", "text": "second\n"})

    assert response == {"ok": True}
    assert mothership.requests["request-1"].workflow_result_parts == ["first\n", "second\n"]


def test_reported_workflow_result_is_used_when_session_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("myteam.workflows.execution.mothership.drain_pty_output", lambda *_args, **_kwargs: None)
    mothership = Mothership()
    session = FakeSession()
    mothership.active = session  # type: ignore[assignment]
    mothership.sessions[session.session_id] = session  # type: ignore[assignment]
    mothership.requests[session.request_id] = RequestRecord(
        request_id=session.request_id,
        kind="workflow",
        status="running",
    )
    mothership.requests[session.request_id].workflow_result_parts.extend(["first\n", "second\n"])

    mothership._handle_workflow_exit(session)  # type: ignore[arg-type]
    mothership._drain_commands()

    assert mothership.results[session.request_id]["status"] == "ok"
    assert mothership.results[session.request_id]["result"]["result_text"] == "first\nsecond\n"
    assert mothership.results[session.request_id]["result"]["transcript"] == "live transcript"


def test_nonzero_exit_keeps_reported_workflow_result_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("myteam.workflows.execution.mothership.drain_pty_output", lambda *_args, **_kwargs: None)
    mothership = Mothership()
    session = FakeSession(exit_code=7)
    mothership.active = session  # type: ignore[assignment]
    mothership.sessions[session.session_id] = session  # type: ignore[assignment]
    mothership.requests[session.request_id] = RequestRecord(
        request_id=session.request_id,
        kind="workflow",
        status="running",
    )
    mothership.requests[session.request_id].workflow_result_parts.append("partial\n")

    mothership._handle_workflow_exit(session)  # type: ignore[arg-type]
    mothership._drain_commands()

    assert mothership.results[session.request_id]["status"] == "exited"
    assert mothership.results[session.request_id]["result"]["exit_code"] == 7
    assert mothership.results[session.request_id]["result"]["result_text"] == "partial\n"


def test_final_result_is_separated_from_unterminated_live_output() -> None:
    mothership = Mothership()
    terminal = FakeTerminal()

    mothership._notice_live_output(b"status line without newline")
    mothership._ensure_final_output_separator(terminal, live_forwarding=True)  # type: ignore[arg-type]

    assert terminal.visual_state_restored is True
    assert terminal.output == b"\r\n"


def test_final_result_separator_ignores_visual_restore_sequences() -> None:
    mothership = Mothership()
    terminal = FakeTerminal()

    mothership._notice_live_output(b"finished\n")
    mothership._notice_live_output(b"\x1b[0m\x1b[?25h")
    mothership._ensure_final_output_separator(terminal, live_forwarding=True)  # type: ignore[arg-type]

    assert terminal.visual_state_restored is True
    assert terminal.cleared is False
    assert terminal.output == b""


def test_final_result_clears_after_screen_rewriting_live_output() -> None:
    mothership = Mothership()
    terminal = FakeTerminal()

    mothership._notice_live_output(b"thinking\x1b[2K\rfinal tui line")
    mothership._ensure_final_output_separator(terminal, live_forwarding=True)  # type: ignore[arg-type]

    assert terminal.visual_state_restored is True
    assert terminal.cleared is True
    assert terminal.output == b""


def test_screen_rewriting_detection_ignores_plain_lines_and_style_controls() -> None:
    assert has_screen_rewriting_control(b"plain line\r\n") is False
    assert has_screen_rewriting_control(b"\x1b[31mred\x1b[0m\r\n") is False
    assert has_screen_rewriting_control(b"line\rrewritten") is True
    assert has_screen_rewriting_control(b"\x1b[2K") is True
