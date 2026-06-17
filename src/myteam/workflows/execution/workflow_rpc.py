"""Unix-socket RPC server for workflow supervision."""
from __future__ import annotations

import socket
import threading
from collections.abc import Callable
from queue import Queue
from typing import Any

from .protocol import (
    KIND_ACK_RESULT,
    KIND_POLL_RESULT,
    KIND_START_WORKFLOW,
    KIND_WORKFLOW_RESULT,
    json_response,
    load_json_object,
    read_all,
)
from .workflow_commands import Command, StartWorkflowCommand
from .workflow_store import WorkflowStore


class WorkflowRpcServer:
    """Handles workflow-supervisor RPC without owning process orchestration."""

    def __init__(
        self,
        *,
        socket_path: str,
        store: WorkflowStore,
        commands: Queue[Command],
        wake: Callable[[], None],
        closed: threading.Event,
    ) -> None:
        self.socket_path = socket_path
        self.store = store
        self.commands = commands
        self.wake = wake
        self.closed = closed
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def start(self):
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(self.socket_path)
        self._server.listen()
        self._server.settimeout(0.1)
        self._thread = threading.Thread(target=self._serve, name="myteam-mothership-rpc", daemon=True)
        self._thread.start()

    def close(self):
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=1)
            self._thread = None

    def _serve(self):
        assert self._server is not None
        while not self.closed.is_set():
            try:
                connection, _ = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle_connection, args=(connection,), daemon=True).start()

    def _handle_connection(self, connection: socket.socket):
        with connection:
            try:
                message = load_json_object(read_all(connection))
                if message.get("kind") == KIND_START_WORKFLOW:
                    response, command = self._accept_start_workflow(message)
                    connection.sendall(json_response(**response))
                    self.commands.put(command)
                    self.wake()
                    return
                response = self._dispatch(message)
            except Exception as exc:  # return friendly errors over the socket
                response = {"ok": False, "error": str(exc)}
            try:
                connection.sendall(json_response(**response))
            except OSError:
                pass

    def _dispatch(self, message: dict[str, Any]) -> dict[str, Any]:
        kind = message.get("kind")
        if kind == KIND_POLL_RESULT:
            return self.store.poll_result(message)
        if kind == KIND_ACK_RESULT:
            return self.store.ack_result(message)
        if kind == KIND_WORKFLOW_RESULT:
            return self.store.report_workflow_result(message)
        return {"ok": False, "error": f"Unsupported RPC kind: {kind!r}"}

    def _accept_start_workflow(self, message: dict[str, Any]) -> tuple[dict[str, Any], StartWorkflowCommand]:
        argv = _require_argv(message, KIND_START_WORKFLOW)
        parent_session_id = message.get("parent_session_id")
        if parent_session_id is not None and not isinstance(parent_session_id, str):
            raise ValueError("parent_session_id must be a string or null.")
        cwd = message.get("cwd")
        if cwd is not None and not isinstance(cwd, str):
            raise ValueError("cwd must be a string or null.")
        input_json = message.get("input_json")
        if input_json is not None and not isinstance(input_json, str):
            raise ValueError("input_json must be a string or null.")

        request_id = self.store.create_request(parent_session_id=parent_session_id).request_id
        command = StartWorkflowCommand(
            request_id=request_id,
            argv=argv,
            parent_session_id=parent_session_id,
            cwd=cwd,
            input_json=input_json,
        )
        return {"ok": True, "request_id": request_id}, command


def _require_argv(message: dict[str, Any], kind: str) -> list[str]:
    argv = message.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) for item in argv):
        raise ValueError(f"{kind} requires a non-empty argv list.")
    return argv
