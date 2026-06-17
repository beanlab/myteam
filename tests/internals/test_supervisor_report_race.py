"""Implementation-level tests for workflow result race handling.

Result reports may arrive immediately before process exit. These tests exercise
the supervisor's storage path directly so race regressions fail with a focused
error instead of a flaky end-to-end timeout.
"""
from __future__ import annotations

import threading

import pytest

from myteam.workflows.execution.live_output import LiveOutputTracker
from myteam.workflows.execution.supervisor import Supervisor
from myteam.workflows.execution.terminal import has_screen_rewriting_control
from myteam.workflows.execution.workflow_store import WorkflowStore


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
    recording = FakeRecording()

    def __init__(self, request_id: str, exit_code: int = 0) -> None:
        self.session_id = request_id
        self.request_id = request_id
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
    store = WorkflowStore()
    record = store.create_request()
    store.mark_running(record.request_id)

    response = store.report_workflow_result(
        {
            "request_id": record.request_id,
            "text": "first\n",
        }
    )
    store.report_workflow_result({"request_id": record.request_id, "text": None})
    store.report_workflow_result({"request_id": record.request_id, "text": "second\n"})

    assert response == {"ok": True}
    assert store.result_text(record.request_id) == "first\nsecond\n"


def test_workflow_store_poll_and_ack_lifecycle() -> None:
    store = WorkflowStore()
    record = store.create_request()

    assert store.poll_result({"request_id": record.request_id}) == {"ok": True, "ready": False}

    parent_session_id = store.complete_request(record.request_id, status="ok", result={"exit_code": 0})

    assert parent_session_id is None
    assert store.poll_result({"request_id": record.request_id}) == {
        "ok": True,
        "ready": True,
        "status": "ok",
        "result": {"exit_code": 0},
    }
    assert store.get_result(record.request_id) == {"status": "ok", "result": {"exit_code": 0}}
    assert store.ack_result({"request_id": record.request_id}) == {"ok": True}
    assert store.get_result(record.request_id) is None
    assert store.parent_session_id(record.request_id) is None


def test_workflow_store_complete_request_returns_parent_session_id() -> None:
    store = WorkflowStore()
    record = store.create_request(parent_session_id="parent-1")

    parent_session_id = store.complete_request(record.request_id, status="ok", result={"exit_code": 0})

    assert parent_session_id == "parent-1"


def test_workflow_store_complete_exit_request_captures_text_and_finalizes() -> None:
    store = WorkflowStore()
    record = store.create_request(parent_session_id="parent-1")
    store.mark_running(record.request_id)
    store.report_workflow_result({"request_id": record.request_id, "text": "first\n"})
    store.report_workflow_result({"request_id": record.request_id, "text": "second\n"})

    parent_session_id = store.complete_exit_request(
        record.request_id,
        exit_code=0,
        transcript="live transcript",
        stderr_transcript="",
    )

    assert parent_session_id == "parent-1"
    assert store.get_result(record.request_id) == {
        "status": "ok",
        "result": {
            "exit_code": 0,
            "result_text": "first\nsecond\n",
            "transcript": "live transcript",
            "stderr_transcript": "",
        },
    }
    with pytest.raises(ValueError, match="Workflow is not active"):
        store.report_workflow_result({"request_id": record.request_id, "text": "late\n"})


def test_workflow_store_rejects_reports_after_final_result() -> None:
    store = WorkflowStore()
    record = store.create_request()
    store.mark_running(record.request_id)
    store.complete_request(record.request_id, status="ok", result={"exit_code": 0})

    with pytest.raises(ValueError, match="Workflow is not active"):
        store.report_workflow_result({"request_id": record.request_id, "text": "late\n"})


def test_workflow_store_accepts_concurrent_result_reports() -> None:
    store = WorkflowStore()
    record = store.create_request()
    store.mark_running(record.request_id)
    expected = {f"part-{index}\n" for index in range(20)}

    threads = [
        threading.Thread(
            target=store.report_workflow_result,
            args=({"request_id": record.request_id, "text": text},),
        )
        for text in expected
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=1)

    assert set(store.result_text(record.request_id).splitlines(keepends=True)) == expected


def test_reported_workflow_result_is_used_when_session_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("myteam.workflows.execution.supervisor.drain_pty_output", lambda *_args, **_kwargs: None)
    supervisor = Supervisor()
    record = supervisor.store.create_request()
    supervisor.store.mark_running(record.request_id)
    session = FakeSession(record.request_id)
    supervisor._stack.active = session  # type: ignore[assignment]
    supervisor._stack.sessions[session.session_id] = session  # type: ignore[assignment]
    supervisor.store.report_workflow_result({"request_id": session.request_id, "text": "first\n"})
    supervisor.store.report_workflow_result({"request_id": session.request_id, "text": "second\n"})

    supervisor._handle_workflow_exit(session)  # type: ignore[arg-type]
    supervisor._drain_commands()

    result = supervisor.store.get_result(session.request_id)
    assert result is not None
    assert result["status"] == "ok"
    assert result["result"]["result_text"] == "first\nsecond\n"
    assert result["result"]["transcript"] == "live transcript"


def test_nonzero_exit_keeps_reported_workflow_result_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("myteam.workflows.execution.supervisor.drain_pty_output", lambda *_args, **_kwargs: None)
    supervisor = Supervisor()
    record = supervisor.store.create_request()
    supervisor.store.mark_running(record.request_id)
    session = FakeSession(record.request_id, exit_code=7)
    supervisor._stack.active = session  # type: ignore[assignment]
    supervisor._stack.sessions[session.session_id] = session  # type: ignore[assignment]
    supervisor.store.report_workflow_result({"request_id": session.request_id, "text": "partial\n"})

    supervisor._handle_workflow_exit(session)  # type: ignore[arg-type]
    supervisor._drain_commands()

    result = supervisor.store.get_result(session.request_id)
    assert result is not None
    assert result["status"] == "exited"
    assert result["result"]["exit_code"] == 7
    assert result["result"]["result_text"] == "partial\n"


def test_final_result_is_separated_from_unterminated_live_output() -> None:
    live_output = LiveOutputTracker()
    terminal = FakeTerminal()

    live_output.notice(b"status line without newline")
    live_output.finish(terminal, enabled=True)  # type: ignore[arg-type]

    assert terminal.visual_state_restored is True
    assert terminal.output == b"\r\n"


def test_final_result_separator_ignores_visual_restore_sequences() -> None:
    live_output = LiveOutputTracker()
    terminal = FakeTerminal()

    live_output.notice(b"finished\n")
    live_output.notice(b"\x1b[0m\x1b[?25h")
    live_output.finish(terminal, enabled=True)  # type: ignore[arg-type]

    assert terminal.visual_state_restored is True
    assert terminal.cleared is False
    assert terminal.output == b""


def test_final_result_clears_after_screen_rewriting_live_output() -> None:
    live_output = LiveOutputTracker()
    terminal = FakeTerminal()

    live_output.notice(b"thinking\x1b[2K\rfinal tui line")
    live_output.finish(terminal, enabled=True)  # type: ignore[arg-type]

    assert terminal.visual_state_restored is True
    assert terminal.cleared is True
    assert terminal.output == b""


def test_screen_rewriting_detection_ignores_plain_lines_and_style_controls() -> None:
    assert has_screen_rewriting_control(b"plain line\r\n") is False
    assert has_screen_rewriting_control(b"\x1b[31mred\x1b[0m\r\n") is False
    assert has_screen_rewriting_control(b"line\rrewritten") is True
    assert has_screen_rewriting_control(b"\x1b[2K") is True
