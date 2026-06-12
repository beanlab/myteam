from __future__ import annotations

import io
import sys

import pytest

from myteam.workflows.agent_result_channel import AgentResultServer, send_agent_result
from myteam.workflows.execution.protocol import (
    ENV_AGENT_SESSION_RESULT_SOCKET,
    ENV_REQUEST_ID,
    ENV_SESSION_ID,
    ENV_SOCKET,
)
from myteam.workflows.results import report_result


def clear_result_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        ENV_AGENT_SESSION_RESULT_SOCKET,
        ENV_SOCKET,
        ENV_SESSION_ID,
        ENV_REQUEST_ID,
    ):
        monkeypatch.delenv(name, raising=False)


def test_agent_result_server_accepts_result() -> None:
    with AgentResultServer() as server:
        send_agent_result(server.socket_path, status="ok", output={"answer": "ok"})

        result = server.wait_for_result(timeout=1)

    assert result is not None
    assert result.status == "ok"
    assert result.output == {"answer": "ok"}


def test_report_result_uses_agent_session_result_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_result_env(monkeypatch)
    with AgentResultServer() as server:
        monkeypatch.setenv(ENV_AGENT_SESSION_RESULT_SOCKET, server.socket_path)

        report_result('{"answer": "ok"}')
        result = server.wait_for_result(timeout=1)

    assert result is not None
    assert result.status == "ok"
    assert result.output == {"answer": "ok"}


def test_report_result_reads_stdin_for_agent_session_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_result_env(monkeypatch)
    with AgentResultServer() as server:
        monkeypatch.setenv(ENV_AGENT_SESSION_RESULT_SOCKET, server.socket_path)
        monkeypatch.setattr(sys, "stdin", io.StringIO('{"from": "stdin"}'))

        report_result()
        result = server.wait_for_result(timeout=1)

    assert result is not None
    assert result.output == {"from": "stdin"}


def test_report_result_preserves_non_json_text_for_agent_session_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_result_env(monkeypatch)
    with AgentResultServer() as server:
        monkeypatch.setenv(ENV_AGENT_SESSION_RESULT_SOCKET, server.socket_path)

        report_result("plain text")
        result = server.wait_for_result(timeout=1)

    assert result is not None
    assert result.output == "plain text"


def test_report_result_falls_back_to_supervisor_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_result_env(monkeypatch)
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeRpcClient:
        def __init__(self, socket_path: str) -> None:
            self.socket_path = socket_path

        def call(self, kind: str, **payload: object) -> dict[str, object]:
            calls.append((kind, {"socket_path": self.socket_path, **payload}))
            return {"ok": True}

    monkeypatch.setattr("myteam.workflows.results.RpcClient", FakeRpcClient)
    monkeypatch.setenv(ENV_SOCKET, "/tmp/supervisor.sock")
    monkeypatch.setenv(ENV_SESSION_ID, "session-1")
    monkeypatch.setenv(ENV_REQUEST_ID, "request-1")

    report_result('{"answer": "fallback"}')

    assert calls == [
        (
            "report_result",
            {
                "socket_path": "/tmp/supervisor.sock",
                "request_id": "request-1",
                "session_id": "session-1",
                "status": "ok",
                "output": {"answer": "fallback"},
            },
        )
    ]


def test_report_result_outside_managed_session_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_result_env(monkeypatch)

    with pytest.raises(RuntimeError, match="No active myteam workflow session"):
        report_result({"answer": "ok"})
