"""Implementation-level tests for workflow result handling.

Result reports may arrive immediately before process exit. These tests exercise
the supervisor's storage path directly so regressions fail with a focused error
instead of a flaky end-to-end timeout.
"""
from __future__ import annotations

import threading

import pytest

from myteam.workflows.execution.supervisor import Supervisor
from myteam.workflows.execution.workflow_store import WorkflowStore


class FakeSession:
    def __init__(self, request_id: str, exit_code: int = 0) -> None:
        self.session_id = request_id
        self.request_id = request_id
        self.exit_code = exit_code

    def poll(self) -> int:
        return self.exit_code

    def wait(self, timeout=None) -> int:
        return self.exit_code

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

    parent_session_id = store.complete_exit_request(record.request_id, exit_code=0)

    assert parent_session_id == "parent-1"
    assert store.get_result(record.request_id) == {
        "status": "ok",
        "result": {
            "exit_code": 0,
            "result_text": "first\nsecond\n",
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
    assert result["result"] == {"exit_code": 0, "result_text": "first\nsecond\n"}


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
    assert result["result"] == {"exit_code": 7, "result_text": "partial\n"}
