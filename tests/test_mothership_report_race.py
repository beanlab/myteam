from myteam.workflows.execution.mothership import Mothership, ReportCommand, RequestRecord


class FakeRecording:
    def snapshot(self) -> str:
        return "transcript"


class FakeSession:
    session_id = "session-1"
    request_id = "request-1"
    nonce = None
    cwd = None
    agent_name = None
    recording = FakeRecording()

    def __init__(self, exit_code: int = 0) -> None:
        self.exit_code = exit_code

    def poll(self) -> int:
        return self.exit_code

    def wait(self, timeout=None) -> int:
        return self.exit_code

    def close(self) -> None:
        pass


def test_report_result_is_stored_as_soon_as_rpc_is_accepted() -> None:
    mothership = Mothership()
    session = FakeSession()
    mothership.active = session
    mothership.sessions[session.session_id] = session
    mothership.requests[session.request_id] = RequestRecord(
        request_id=session.request_id,
        kind="agent_session",
        status="running",
        session_id=session.session_id,
    )

    response, _command = mothership._accept_report_result(
        {
            "request_id": session.request_id,
            "session_id": session.session_id,
            "status": "ok",
            "output": {"answer": "ok"},
        }
    )

    assert response == {"ok": True}
    assert mothership.results[session.request_id]["status"] == "ok"
    assert mothership.results[session.request_id]["result"]["output"] == {"answer": "ok"}


def test_reported_result_wins_if_session_exits_before_report_command_is_drained() -> None:
    mothership = Mothership()
    session = FakeSession()
    mothership.active = session
    mothership.sessions[session.session_id] = session
    mothership.requests[session.request_id] = RequestRecord(
        request_id=session.request_id,
        kind="agent_session",
        status="running",
        session_id=session.session_id,
    )
    mothership._pending_reports[session.request_id] = ReportCommand(
        request_id=session.request_id,
        session_id=session.session_id,
        status="ok",
        output={"answer": "ok"},
    )

    mothership._handle_session_exit(session)

    assert mothership.results[session.request_id]["status"] == "ok"
    assert mothership.results[session.request_id]["result"]["output"] == {"answer": "ok"}


def test_late_report_can_override_exited_result_for_completed_session() -> None:
    mothership = Mothership()
    session = FakeSession()
    mothership.active = session
    mothership.sessions[session.session_id] = session
    mothership.requests[session.request_id] = RequestRecord(
        request_id=session.request_id,
        kind="agent_session",
        status="running",
        session_id=session.session_id,
    )

    mothership._handle_session_exit(session)
    assert session.request_id not in mothership.results
    assert session.request_id in mothership._pending_exits

    response, _command = mothership._accept_report_result(
        {
            "request_id": session.request_id,
            "session_id": session.session_id,
            "status": "ok",
            "output": {"answer": "late ok"},
        }
    )

    assert response == {"ok": True}
    assert mothership.results[session.request_id]["status"] == "ok"
    assert mothership.results[session.request_id]["result"]["output"] == {"answer": "late ok"}


def test_clean_exit_becomes_none_output_after_late_report_grace_expires() -> None:
    mothership = Mothership()
    session = FakeSession()
    mothership.active = session
    mothership.sessions[session.session_id] = session
    mothership.requests[session.request_id] = RequestRecord(
        request_id=session.request_id,
        kind="agent_session",
        status="running",
        session_id=session.session_id,
    )

    mothership._handle_session_exit(session)
    pending_session, code, _deadline = mothership._pending_exits[session.request_id]
    mothership._pending_exits[session.request_id] = (pending_session, code, 0)
    mothership._finalize_expired_exits()

    assert mothership.results[session.request_id]["status"] == "ok"
    assert mothership.results[session.request_id]["result"]["output"] is None


def test_nonzero_exit_is_reported_after_late_report_grace_expires() -> None:
    mothership = Mothership()
    session = FakeSession(exit_code=7)
    mothership.active = session
    mothership.sessions[session.session_id] = session
    mothership.requests[session.request_id] = RequestRecord(
        request_id=session.request_id,
        kind="agent_session",
        status="running",
        session_id=session.session_id,
    )

    mothership._handle_session_exit(session)
    pending_session, code, _deadline = mothership._pending_exits[session.request_id]
    mothership._pending_exits[session.request_id] = (pending_session, code, 0)
    mothership._finalize_expired_exits()

    assert mothership.results[session.request_id]["status"] == "exited"
    assert mothership.results[session.request_id]["result"]["output"] == {"exit_code": 7}
