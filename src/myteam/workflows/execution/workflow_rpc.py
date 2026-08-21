"""Unix-socket RPC server for workflow supervision."""
from __future__ import annotations

import socket
import threading
from collections.abc import Callable
from pathlib import Path
from queue import Queue
from typing import Any

from .protocol import (
    KIND_ACK_RESULT,
    KIND_GET_STACK,
    KIND_POLL_RESULT,
    KIND_REGISTER_AGENT,
    KIND_START_WORKFLOW,
    KIND_UNREGISTER_AGENT,
    KIND_WORKFLOW_RESULT,
    json_response,
    load_json_object,
    read_all,
)
from .workflow_commands import Command, StartWorkflowCommand
from .workflow_store import AgentSessionRecord, WorkflowStore


class WorkflowRpcServer:
    """Handles workflow-supervisor RPC without owning process orchestration."""

    def __init__(self, *, socket_path: str, store: WorkflowStore, commands: Queue[Command], wake: Callable[[], None], closed: threading.Event) -> None:
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
        self._thread = threading.Thread(target=self._serve, name="myteam-supervisor-rpc", daemon=True)
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
        registered_nonce: str | None = None
        created_registration = False
        with connection:
            try:
                message = load_json_object(read_all(connection))
                kind = message.get("kind")
                if kind == KIND_START_WORKFLOW:
                    response, command = self._accept_start_workflow(message)
                    connection.sendall(json_response(**response))
                    self.commands.put(command)
                    self.wake()
                    return
                if kind == KIND_REGISTER_AGENT:
                    record = _agent_record(message)
                    created_registration = self.store.register_agent(record)
                    registered_nonce = record.nonce
                    response = {"ok": True}
                else:
                    response = self._dispatch(message)
            except Exception as exc:
                response = {"ok": False, "error": str(exc)}
            try:
                connection.sendall(json_response(**response))
            except OSError:
                if created_registration and registered_nonce is not None:
                    self.store.unregister_agent(registered_nonce)

    def _dispatch(self, message: dict[str, Any]) -> dict[str, Any]:
        kind = message.get("kind")
        if kind == KIND_POLL_RESULT:
            return self.store.poll_result(message)
        if kind == KIND_ACK_RESULT:
            return self.store.ack_result(message)
        if kind == KIND_WORKFLOW_RESULT:
            return self.store.report_workflow_result(message)
        if kind == KIND_UNREGISTER_AGENT:
            nonce = _required_string(message, "nonce", KIND_UNREGISTER_AGENT)
            self.store.unregister_agent(nonce)
            return {"ok": True}
        if kind == KIND_GET_STACK:
            return {"ok": True, "complete": True, "entries": self.store.stack_snapshot()}
        return {"ok": False, "error": f"Unsupported RPC kind: {kind!r}"}

    def _accept_start_workflow(self, message: dict[str, Any]) -> tuple[dict[str, Any], StartWorkflowCommand]:
        argv = _require_argv(message, KIND_START_WORKFLOW)
        workflow_path = _required_string(message, "workflow_path", KIND_START_WORKFLOW)
        path = Path(workflow_path)
        if not path.is_absolute() or str(path.resolve()) != workflow_path:
            raise ValueError("workflow_path must be an absolute resolved path.")
        parent_session_id = _optional_string(message, "parent_session_id")
        parent_agent_nonce = _optional_string(message, "parent_agent_nonce")
        cwd = _optional_string(message, "cwd")
        input_json = _optional_string(message, "input_json")
        self.store.validate_workflow_parent(parent_session_id, parent_agent_nonce)

        record = self.store.create_request(
            workflow_path=workflow_path,
            parent_session_id=parent_session_id,
            parent_agent_nonce=parent_agent_nonce,
        )
        command = StartWorkflowCommand(
            request_id=record.request_id,
            argv=argv,
            workflow_path=workflow_path,
            parent_session_id=parent_session_id,
            parent_agent_nonce=parent_agent_nonce,
            cwd=cwd,
            input_json=input_json,
        )
        return {"ok": True, "request_id": record.request_id}, command


def _agent_record(message: dict[str, Any]) -> AgentSessionRecord:
    return AgentSessionRecord(
        nonce=_required_string(message, "nonce", KIND_REGISTER_AGENT),
        workflow_invocation_id=_required_string(message, "workflow_invocation_id", KIND_REGISTER_AGENT),
        parent_agent_nonce=_optional_string(message, "parent_agent_nonce"),
        name=_required_string(message, "name", KIND_REGISTER_AGENT, allow_empty=True),
        agent=_required_string(message, "agent", KIND_REGISTER_AGENT),
        model=_optional_string(message, "model"),
        session_id=_optional_string(message, "session_id"),
    )


def _required_string(message: dict[str, Any], field: str, kind: str, *, allow_empty: bool = False) -> str:
    value = message.get(field)
    if not isinstance(value, str) or (not value and not allow_empty):
        raise ValueError(f"{kind} requires {field} to be a string" + ("." if allow_empty else " containing a value."))
    return value


def _optional_string(message: dict[str, Any], field: str) -> str | None:
    value = message.get(field)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{field} must be a string or null.")
    return value


def _require_argv(message: dict[str, Any], kind: str) -> list[str]:
    argv = message.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) for item in argv):
        raise ValueError(f"{kind} requires a non-empty argv list.")
    return argv
