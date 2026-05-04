from __future__ import annotations

from collections.abc import Mapping
import json
import os
import secrets
import socket
import tempfile
import threading
from pathlib import Path
from typing import Any


RESULT_SOCKET_ENV = "MYTEAM_RESULT_SOCKET"
RESULT_TOKEN_ENV = "MYTEAM_RESULT_TOKEN"


class ResultChannel:
    def __init__(self) -> None:
        self.socket_path = ""
        self.token = secrets.token_urlsafe(18)
        self.payload: Any | None = None
        self.closed = threading.Event()
        self._result_ready = threading.Event()
        self._tmpdir: tempfile.TemporaryDirectory[str] | None = None
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "ResultChannel":
        self._tmpdir = tempfile.TemporaryDirectory(prefix="myteam-workflow-")
        self.socket_path = str(Path(self._tmpdir.name) / "result.sock")
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(self.socket_path)
        self._server.listen()
        self._server.settimeout(0.1)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.closed.set()
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=1)
        if self._tmpdir is not None:
            self._tmpdir.cleanup()

    @property
    def env(self) -> dict[str, str]:
        return {
            RESULT_SOCKET_ENV: self.socket_path,
            RESULT_TOKEN_ENV: self.token,
        }

    def wait(self, timeout: float | None = None) -> Any | None:
        if not self._result_ready.wait(timeout):
            return None
        return self.payload

    def _serve(self) -> None:
        assert self._server is not None
        while not self.closed.is_set():
            try:
                connection, _ = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with connection:
                response = self._handle_message(_read_socket_message(connection))
                try:
                    connection.sendall(json.dumps(response).encode("utf-8") + b"\n")
                except OSError:
                    pass

    def _handle_message(self, raw: bytes) -> dict[str, Any]:
        try:
            message = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"ok": False, "error": "Invalid JSON payload."}

        if not isinstance(message, dict):
            return {"ok": False, "error": "Result message must be a JSON object."}
        if message.get("version") != 1 or message.get("kind") != "result":
            return {"ok": False, "error": "Unsupported result message."}
        if message.get("token") != self.token:
            return {"ok": False, "error": "Invalid workflow result token."}
        if "payload" not in message:
            return {"ok": False, "error": "Missing workflow result payload."}
        if self._result_ready.is_set():
            return {"ok": False, "error": "Workflow result already recorded."}

        self.payload = message["payload"]
        self._result_ready.set()
        return {"ok": True}


def submit_result_payload(
    payload: Any,
    *,
    socket_path: str | None = None,
    token: str | None = None,
) -> None:
    resolved_socket = socket_path or os.environ.get(RESULT_SOCKET_ENV)
    resolved_token = token or os.environ.get(RESULT_TOKEN_ENV)
    if not resolved_socket or not resolved_token:
        raise ValueError("Missing MYTEAM_RESULT_SOCKET or MYTEAM_RESULT_TOKEN.")

    message = {
        "version": 1,
        "kind": "result",
        "token": resolved_token,
        "payload": payload,
    }

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.connect(resolved_socket)
        connection.sendall(json.dumps(message).encode("utf-8"))
        connection.shutdown(socket.SHUT_WR)
        response = _read_socket_message(connection)

    try:
        ack = json.loads(response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Workflow runner returned an invalid acknowledgement.") from exc

    if not ack.get("ok"):
        raise ValueError(str(ack.get("error") or "Workflow runner rejected the result."))


def _read_socket_message(connection: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = connection.recv(4096)
        if not chunk:
            return b"".join(chunks).strip()
        chunks.append(chunk)
