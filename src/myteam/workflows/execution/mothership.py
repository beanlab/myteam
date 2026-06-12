"""Workflow supervisor: coordinates workflow RPC requests.

This module is intentionally workflow-only. Agent sessions are owned by
`run_agent` in `myteam.workflows.agent_session` and report results over the
per-agent result channel, not through this supervisor.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from queue import Empty, Queue
import secrets
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Literal

from .protocol import (
    ENV_SOCKET,
    ENV_WORKFLOW_INPUT_JSON,
    ENV_WORKFLOW_INVOCATION_ID,
    KIND_ACK_RESULT,
    KIND_POLL_RESULT,
    KIND_START_WORKFLOW,
    json_response,
    load_json_object,
    read_all,
    safe_unlink,
)


@dataclass
class StartWorkflowCommand:
    request_id: str
    argv: list[str]
    parent_session_id: str | None
    cwd: str | None
    input_json: str | None


@dataclass
class WorkflowCompletedCommand:
    request_id: str
    status: str
    result: Any


Command = StartWorkflowCommand | WorkflowCompletedCommand


@dataclass
class RequestRecord:
    request_id: str
    kind: Literal["workflow"]
    status: Literal["pending", "running", "ok", "error", "exited"] = "pending"
    parent_session_id: str | None = None
    result: Any = None


class Mothership:
    """Small workflow supervisor and nested `myteam start` RPC server.

    This transitional implementation still launches workflow processes with
    captured stdout/stderr. The next supervisor-focused unit should replace this
    with the documented PTY/process-group stack behavior.
    """

    def __init__(self) -> None:
        self.socket_path = ""
        self.requests: dict[str, RequestRecord] = {}
        self.results: dict[str, dict[str, Any]] = {}
        self.workflow_threads: dict[str, threading.Thread] = {}

        self._tmpdir: tempfile.TemporaryDirectory[str] | None = None
        self._server: socket.socket | None = None
        self._server_thread: threading.Thread | None = None
        self._closed = threading.Event()
        self._commands: Queue[Command] = Queue()

    def __enter__(self) -> "Mothership":
        self._tmpdir = tempfile.TemporaryDirectory(prefix="myteam-mothership-")
        self.socket_path = str(Path(self._tmpdir.name) / "mothership.sock")

        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(self.socket_path)
        self._server.listen()
        self._server.settimeout(0.1)
        self._server_thread = threading.Thread(target=self._serve, name="myteam-mothership-rpc", daemon=True)
        self._server_thread.start()
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        self._closed.set()
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
        if self._server_thread is not None:
            self._server_thread.join(timeout=1)
        for thread in list(self.workflow_threads.values()):
            thread.join(timeout=1)
        if self.socket_path:
            safe_unlink(self.socket_path)
        if self._tmpdir is not None:
            self._tmpdir.cleanup()

    def start_top_level_workflow(self, *, argv: list[str], cwd: str | None, input_json: str | None) -> str:
        request_id = self._new_request_id()
        self.requests[request_id] = RequestRecord(request_id=request_id, kind="workflow", status="pending")
        self._commands.put(
            StartWorkflowCommand(
                request_id=request_id,
                argv=argv,
                parent_session_id=None,
                cwd=cwd,
                input_json=input_json,
            )
        )
        return request_id

    def run_until_complete(self, top_request_id: str) -> dict[str, Any] | None:
        """Run queued workflow requests until the top-level request finishes."""

        while not self._closed.is_set():
            self._drain_commands()

            if top_request_id in self.results:
                return self.results[top_request_id]
            if self._commands.empty() and not self._has_running_workflows():
                return None

            time.sleep(0.05)

        return None

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
            try:
                message = load_json_object(read_all(connection))
                kind = message.get("kind")
                if kind == KIND_START_WORKFLOW:
                    response, command = self._accept_start_workflow(message)
                    connection.sendall(json_response(**response))
                    self._commands.put(command)
                    return
                if kind == KIND_POLL_RESULT:
                    response = self._poll_result(message)
                elif kind == KIND_ACK_RESULT:
                    response = self._ack_result(message)
                else:
                    response = {"ok": False, "error": f"Unsupported RPC kind: {kind!r}"}
            except Exception as exc:  # return friendly errors over the socket
                response = {"ok": False, "error": str(exc)}
            try:
                connection.sendall(json_response(**response))
            except OSError:
                pass

    def _accept_start_workflow(self, message: dict[str, Any]) -> tuple[dict[str, Any], StartWorkflowCommand]:
        argv = self._require_argv(message, KIND_START_WORKFLOW)
        parent_session_id = message.get("parent_session_id")
        if parent_session_id is not None and not isinstance(parent_session_id, str):
            raise ValueError("parent_session_id must be a string or null.")
        cwd = message.get("cwd")
        if cwd is not None and not isinstance(cwd, str):
            raise ValueError("cwd must be a string or null.")
        input_json = message.get("input_json")
        if input_json is not None and not isinstance(input_json, str):
            raise ValueError("input_json must be a string or null.")

        request_id = self._new_request_id()
        self.requests[request_id] = RequestRecord(
            request_id=request_id,
            kind="workflow",
            status="pending",
            parent_session_id=parent_session_id,
        )
        command = StartWorkflowCommand(
            request_id=request_id,
            argv=argv,
            parent_session_id=parent_session_id,
            cwd=cwd,
            input_json=input_json,
        )
        return {"ok": True, "request_id": request_id}, command

    def _poll_result(self, message: dict[str, Any]) -> dict[str, Any]:
        request_id = message.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("poll_result requires request_id.")
        if request_id not in self.results:
            return {"ok": True, "ready": False}
        return {"ok": True, "ready": True, **self.results[request_id]}

    def _ack_result(self, message: dict[str, Any]) -> dict[str, Any]:
        request_id = message.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("ack_result requires request_id.")
        self.results.pop(request_id, None)
        self.requests.pop(request_id, None)
        return {"ok": True}

    def _drain_commands(self) -> None:
        while True:
            try:
                command = self._commands.get_nowait()
            except Empty:
                return
            if isinstance(command, StartWorkflowCommand):
                self._start_workflow(command)
            else:
                self._complete_workflow(command)

    def _start_workflow(self, command: StartWorkflowCommand) -> None:
        record = self.requests[command.request_id]
        record.status = "running"

        thread = threading.Thread(
            target=self._run_workflow_process,
            args=(command,),
            name=f"myteam-workflow-{command.request_id}",
            daemon=True,
        )
        self.workflow_threads[command.request_id] = thread
        thread.start()

    def _run_workflow_process(self, command: StartWorkflowCommand) -> None:
        env = {
            **os.environ,
            ENV_SOCKET: self.socket_path,
            ENV_WORKFLOW_INVOCATION_ID: command.request_id,
        }
        if command.input_json is not None:
            env[ENV_WORKFLOW_INPUT_JSON] = command.input_json

        try:
            completed = subprocess.run(
                command.argv,
                cwd=command.cwd,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            status = "ok" if completed.returncode == 0 else "exited"
            result = {
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        except Exception as exc:
            status = "error"
            result = {"message": str(exc)}

        self._commands.put(WorkflowCompletedCommand(command.request_id, status, result))

    def _complete_workflow(self, command: WorkflowCompletedCommand) -> None:
        self.workflow_threads.pop(command.request_id, None)
        self._store_result(command.request_id, status=command.status, result=command.result)

    def _store_result(self, request_id: str, *, status: str, result: Any) -> None:
        self.results[request_id] = {"status": status, "result": result}
        record = self.requests.get(request_id)
        if record is not None:
            record.status = status if status in {"ok", "error", "exited"} else "ok"
            record.result = result

    def _has_running_workflows(self) -> bool:
        return any(thread.is_alive() for thread in self.workflow_threads.values())

    def _require_argv(self, message: dict[str, Any], kind: str) -> list[str]:
        argv = message.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(item, str) for item in argv):
            raise ValueError(f"{kind} requires a non-empty argv list.")
        return argv

    def _new_request_id(self) -> str:
        return secrets.token_urlsafe(12)

