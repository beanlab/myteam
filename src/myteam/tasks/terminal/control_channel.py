from __future__ import annotations

from dataclasses import dataclass
import json
import secrets
import socket
import tempfile
import threading
from pathlib import Path
from typing import Any

from .result_channel import _read_socket_message
from .session_registry import load_channel_details, register_channel, unregister_channel


@dataclass(frozen=True)
class ChildTaskRequest:
    task: str
    input: Any | None = None


class ControlChannel:
    def __init__(self, *, session_nonce: str | None = None) -> None:
        self.socket_path = ""
        self.token = secrets.token_urlsafe(18)
        self.request: ChildTaskRequest | None = None
        self.closed = threading.Event()
        self._request_ready = threading.Event()
        self._tmpdir: tempfile.TemporaryDirectory[str] | None = None
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._session_nonce = session_nonce

    def __enter__(self) -> "ControlChannel":
        self._tmpdir = tempfile.TemporaryDirectory(prefix="myteam-task-")
        self.socket_path = str(Path(self._tmpdir.name) / "control.sock")
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(self.socket_path)
        self._server.listen()
        self._server.settimeout(0.1)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        if self._session_nonce is not None:
            register_channel(
                self._session_nonce,
                "control",
                socket_path=self.socket_path,
                token=self.token,
            )
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        if self._session_nonce is not None:
            unregister_channel(self._session_nonce, "control")
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

    def wait(self, timeout: float | None = None) -> ChildTaskRequest | None:
        if not self._request_ready.wait(timeout):
            return None
        return self.request

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
            return {"ok": False, "error": "Control message must be a JSON object."}
        if message.get("version") != 1 or message.get("kind") != "child_task_request":
            return {"ok": False, "error": "Unsupported control message."}
        if message.get("token") != self.token:
            return {"ok": False, "error": "Invalid task control token."}
        task = message.get("task")
        if not isinstance(task, str) or not task:
            return {"ok": False, "error": "Missing child task name."}
        if self._request_ready.is_set():
            return {"ok": False, "error": "Child task request already recorded."}

        self.request = ChildTaskRequest(
            task=task,
            input=message["input"] if "input" in message else None,
        )
        self._request_ready.set()
        return {"ok": True}


def submit_child_task_request(
    task: str,
    input: Any | None = None,
    *,
    session_nonce: str | None = None,
    socket_path: str | None = None,
    token: str | None = None,
) -> None:
    if session_nonce is not None:
        resolved_socket, resolved_token = _resolve_channel_details(session_nonce, kind="control")
        if socket_path is not None:
            resolved_socket = socket_path
        if token is not None:
            resolved_token = token
    else:
        resolved_socket = socket_path
        resolved_token = token
        if not resolved_socket or not resolved_token:
            raise ValueError("Missing session nonce.")

    message = {
        "version": 1,
        "kind": "child_task_request",
        "token": resolved_token,
        "task": task,
    }
    if session_nonce is not None:
        message["nonce"] = session_nonce
    if input is not None:
        message["input"] = input

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.connect(resolved_socket)
        connection.sendall(json.dumps(message).encode("utf-8"))
        connection.shutdown(socket.SHUT_WR)
        response = _read_socket_message(connection)

    try:
        ack = json.loads(response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Task runner returned an invalid acknowledgement.") from exc

    if not ack.get("ok"):
        raise ValueError(str(ack.get("error") or "Task runner rejected the child task request."))


def _resolve_channel_details(session_nonce: str, *, kind: str) -> tuple[str, str]:
    try:
        return load_channel_details(session_nonce, kind)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
