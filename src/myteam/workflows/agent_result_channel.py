"""Per-`run_agent` result channel used by `myteam result`.

This socket is intentionally separate from the workflow supervisor socket. The
supervisor coordinates workflow process trees; each `run_agent` invocation owns
one result channel for the child agent session it launched.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from queue import Empty, Queue
import socket
import tempfile
import threading
from pathlib import Path
from typing import Any

from .execution.protocol import VERSION, json_response, read_all, safe_unlink

KIND_AGENT_SESSION_RESULT = "agent_session_result"


@dataclass(frozen=True)
class AgentReportedResult:
    status: str
    output: Any


class AgentResultServer:
    """Small one-process Unix-socket server for agent session results."""

    def __init__(self) -> None:
        self.socket_path = ""
        self._tmpdir: tempfile.TemporaryDirectory[str] | None = None
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._closed = threading.Event()
        self._results: Queue[AgentReportedResult] = Queue()

    def __enter__(self) -> "AgentResultServer":
        self._tmpdir = tempfile.TemporaryDirectory(prefix="myteam-agent-result-")
        self.socket_path = str(Path(self._tmpdir.name) / "result.sock")
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(self.socket_path)
        self._server.listen()
        self._server.settimeout(0.1)
        self._thread = threading.Thread(
            target=self._serve,
            name="myteam-agent-result-channel",
            daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        self.close()

    def wait_for_result(self, timeout: float | None = None) -> AgentReportedResult | None:
        try:
            return self._results.get(timeout=timeout)
        except Empty:
            return None

    def close(self) -> None:
        self._closed.set()
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=1)
            self._thread = None
        if self.socket_path:
            safe_unlink(self.socket_path)
        if self._tmpdir is not None:
            self._tmpdir.cleanup()
            self._tmpdir = None

    def _serve(self) -> None:
        assert self._server is not None
        while not self._closed.is_set():
            try:
                connection, _ = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle_connection, args=(connection,), daemon=True).start()

    def _handle_connection(self, connection: socket.socket) -> None:
        with connection:
            reported_result: AgentReportedResult | None = None
            try:
                message = _load_agent_result_message(read_all(connection))
                reported_result = AgentReportedResult(
                    status=message["status"],
                    output=message.get("output"),
                )
                response = {"ok": True}
            except Exception as exc:
                response = {"ok": False, "error": str(exc)}
            try:
                connection.sendall(json_response(**response))
            except OSError:
                pass
            if reported_result is not None:
                self._results.put(reported_result)


def send_agent_result(socket_path: str, *, status: str, output: Any) -> None:
    """Send one reported result to an AgentResultServer."""

    message = {
        "version": VERSION,
        "kind": KIND_AGENT_SESSION_RESULT,
        "status": status,
        "output": output,
    }
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.connect(socket_path)
        connection.sendall(json.dumps(message).encode("utf-8"))
        connection.shutdown(socket.SHUT_WR)
        raw = read_all(connection)

    try:
        response = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Agent result channel returned an invalid JSON response.") from exc

    if not isinstance(response, dict):
        raise RuntimeError("Agent result channel returned a non-object JSON response.")
    if not response.get("ok"):
        raise RuntimeError(str(response.get("error") or "Agent result report failed."))


def _load_agent_result_message(raw: bytes) -> dict[str, Any]:
    try:
        message = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid JSON payload.") from exc
    if not isinstance(message, dict):
        raise ValueError("Agent result payload must be a JSON object.")
    if message.get("version") != VERSION:
        raise ValueError("Unsupported agent result protocol version.")
    if message.get("kind") != KIND_AGENT_SESSION_RESULT:
        raise ValueError("Unsupported agent result RPC kind.")
    status = message.get("status", "ok")
    if not isinstance(status, str) or not status:
        raise ValueError("status must be a string.")
    message["status"] = status
    return message
