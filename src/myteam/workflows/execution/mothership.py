"""Workflow supervisor: coordinates workflow RPC requests and PTY handoff.

This module is workflow-only. Agent sessions are owned by `run_agent` in
`myteam.workflows.agent_session` and report results over the per-agent result
channel, not through this supervisor.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from queue import Empty, Queue
import secrets
import select
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Literal

from .protocol import (
    ENV_SOCKET,
    ENV_WORKFLOW_INPUT_JSON,
    ENV_WORKFLOW_INVOCATION_ID,
    KIND_ACK_RESULT,
    KIND_POLL_RESULT,
    KIND_START_WORKFLOW,
    KIND_WORKFLOW_RESULT,
    json_response,
    load_json_object,
    read_all,
    safe_unlink,
)
from .pty_forwarding import drain_pty_output, os_fd_writer, pump_pty_once
from .pty_process import ManagedPtyProcess
from .terminal import RealTerminal, Winsize


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
    workflow_result_parts: list[str] = field(default_factory=list)


class Mothership:
    """Small workflow supervisor and nested `myteam start` RPC server.

    Workflows are launched under PTYs. The supervisor owns the user's real
    terminal and forwards input/output to one active workflow at a time. Nested
    `myteam start` requests suspend the active workflow process group, run the
    child workflow, store the child process result, and then resume the parent.
    """

    def __init__(self) -> None:
        self.socket_path = ""
        self.requests: dict[str, RequestRecord] = {}
        self.results: dict[str, dict[str, Any]] = {}
        self.active: ManagedPtyProcess | None = None
        self.stack: list[ManagedPtyProcess] = []
        self.sessions: dict[str, ManagedPtyProcess] = {}

        self._tmpdir: tempfile.TemporaryDirectory[str] | None = None
        self._server: socket.socket | None = None
        self._server_thread: threading.Thread | None = None
        self._closed = threading.Event()
        self._commands: Queue[Command] = Queue()
        self._wakeup_r = -1
        self._wakeup_w = -1
        self._terminal = RealTerminal(on_resize=self._resize_sessions)

    def __enter__(self) -> "Mothership":
        self._tmpdir = tempfile.TemporaryDirectory(prefix="myteam-mothership-")
        self.socket_path = str(Path(self._tmpdir.name) / "mothership.sock")
        self._wakeup_r, self._wakeup_w = os.pipe()
        os.set_blocking(self._wakeup_r, False)

        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(self.socket_path)
        self._server.listen()
        self._server.settimeout(0.1)
        self._server_thread = threading.Thread(target=self._serve, name="myteam-mothership-rpc", daemon=True)
        self._server_thread.start()
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        self._terminal.flush_input()
        self._terminal.restore()
        self._closed.set()
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
        if self._server_thread is not None:
            self._server_thread.join(timeout=1)
        for session in list(self.sessions.values()):
            session.terminate()
            session.close()
        for fd in (self._wakeup_r, self._wakeup_w):
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
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
        self._wake()
        return request_id

    def run_until_complete(self, top_request_id: str) -> dict[str, Any] | None:
        """Run workflow PTY forwarding until the top-level request finishes."""

        with self._terminal as terminal:
            live_forwarding = sys.stdout.isatty()
            while not self._closed.is_set():
                self._drain_commands()
                self._reap_exited_active_session(terminal=terminal, live_forwarding=live_forwarding)

                if top_request_id in self.results:
                    return self.results[top_request_id]
                if self.active is None and not self.stack and self._commands.empty():
                    return None

                if self.active is None:
                    ready, _, _ = select.select([self._wakeup_r], [], [], 0.1)
                    if self._wakeup_r in ready:
                        self._drain_wakeup_pipe()
                    continue

                stderr_writer = _stderr_writer() if live_forwarding else None
                activity = pump_pty_once(
                    self.active,
                    terminal,
                    timeout=0.1,
                    stdout_writer=terminal.write_stdout if live_forwarding else None,
                    stderr_writer=stderr_writer,
                    forward_stdout=live_forwarding,
                    forward_stderr=live_forwarding,
                    extra_fds=[self._wakeup_r],
                    preempt_on_extra_fd=True,
                )
                if self._wakeup_r in activity.ready_extra_fds:
                    self._drain_wakeup_pipe()
                    continue
                if activity.stdout_eof:
                    self._handle_workflow_exit(
                        self.active,
                        stdout_writer=terminal.write_stdout if live_forwarding else None,
                        stderr_writer=stderr_writer,
                        forward_stdout=live_forwarding,
                        forward_stderr=live_forwarding,
                    )
                    continue

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
                    self._wake()
                    return
                if kind == KIND_POLL_RESULT:
                    response = self._poll_result(message)
                elif kind == KIND_ACK_RESULT:
                    response = self._ack_result(message)
                elif kind == KIND_WORKFLOW_RESULT:
                    response = self._report_workflow_result(message)
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

    def _report_workflow_result(self, message: dict[str, Any]) -> dict[str, Any]:
        request_id = message.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("workflow_result requires request_id.")
        text = message.get("text")
        if text is not None and not isinstance(text, str):
            raise ValueError("workflow_result text must be a string or null.")
        record = self.requests.get(request_id)
        if record is None:
            raise ValueError("Unknown workflow request_id.")
        if record.status not in {"pending", "running"}:
            raise ValueError("Workflow is not active.")
        if text is not None:
            record.workflow_result_parts.append(text)
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

        if command.parent_session_id is not None:
            if self.active is None or self.active.session_id != command.parent_session_id:
                self._store_result(
                    command.request_id,
                    status="error",
                    result={
                        "exit_code": 1,
                        "result_text": "",
                        "error_text": "Parent workflow is not the active managed workflow.\n",
                    },
                )
                return
            self._terminal.flush_input()
            self.active.suspend()
            self.stack.append(self.active)
            self.active = None
            if sys.stdout.isatty():
                self._terminal.clear()
            self._terminal.flush_input()
        elif self.active is not None:
            self._store_result(
                command.request_id,
                status="error",
                result={
                    "exit_code": 1,
                    "result_text": "",
                    "error_text": "Another workflow is already active.\n",
                },
            )
            return

        session = self._launch_workflow(command)
        self.sessions[session.session_id] = session
        self.active = session
        if sys.stdout.isatty():
            self._terminal.clear()
        self._terminal.flush_input()

    def _launch_workflow(self, command: StartWorkflowCommand) -> ManagedPtyProcess:
        env = {
            **os.environ,
            ENV_SOCKET: self.socket_path,
            ENV_WORKFLOW_INVOCATION_ID: command.request_id,
        }
        if command.input_json is not None:
            env[ENV_WORKFLOW_INPUT_JSON] = command.input_json

        return ManagedPtyProcess.launch(
            session_id=command.request_id,
            request_id=command.request_id,
            argv=command.argv,
            env=env,
            cwd=command.cwd,
            winsize=self._terminal.winsize(),
            parent_session_id=command.parent_session_id,
            merge_stderr=False,
        )

    def _complete_workflow(self, command: WorkflowCompletedCommand) -> None:
        self._store_result(command.request_id, status=command.status, result=command.result)
        record = self.requests.get(command.request_id)
        if record is not None and record.parent_session_id is not None:
            self._resume_previous_workflow()
        else:
            self._wake()

    def _handle_workflow_exit(
        self,
        session: ManagedPtyProcess,
        *,
        stdout_writer=None,
        stderr_writer=None,
        forward_stdout: bool = False,
        forward_stderr: bool = False,
    ) -> None:
        code = session.poll()
        if code is None:
            try:
                code = session.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                code = None
        exit_code = code if isinstance(code, int) else 1
        drain_pty_output(
            session,
            stdout_writer=stdout_writer,
            stderr_writer=stderr_writer,
            forward_stdout=forward_stdout,
            forward_stderr=forward_stderr,
        )
        record = self.requests.get(session.request_id)
        result_text = "" if record is None else "".join(record.workflow_result_parts)
        result = {
            "exit_code": exit_code,
            "result_text": result_text,
            "transcript": _normalize_pty_text(session.recording.snapshot()),
            "stderr_transcript": session.stderr_snapshot(),
        }
        self._remove_session(session)
        self._commands.put(
            WorkflowCompletedCommand(
                request_id=session.request_id,
                status="ok" if exit_code == 0 else "exited",
                result=result,
            )
        )
        self._wake()

    def _reap_exited_active_session(self, *, terminal: RealTerminal, live_forwarding: bool) -> None:
        if self.active is not None and self.active.poll() is not None:
            self._handle_workflow_exit(
                self.active,
                stdout_writer=terminal.write_stdout if live_forwarding else None,
                stderr_writer=_stderr_writer() if live_forwarding else None,
                forward_stdout=live_forwarding,
                forward_stderr=live_forwarding,
            )

    def _resume_previous_workflow(self) -> None:
        if self.stack:
            self._terminal.flush_input()
            self.active = self.stack.pop()
            self.active.resume()
            if sys.stdout.isatty():
                self._terminal.clear()
            self._terminal.flush_input()
        else:
            self.active = None
            self._wake()

    def _remove_session(self, session: ManagedPtyProcess) -> None:
        self.sessions.pop(session.session_id, None)
        if self.active is session:
            self.active = None
        session.close()

    def _resize_sessions(self, winsize: Winsize) -> None:
        for session in self.sessions.values():
            session.resize(winsize)

    def _store_result(self, request_id: str, *, status: str, result: Any) -> None:
        self.results[request_id] = {"status": status, "result": result}
        record = self.requests.get(request_id)
        if record is not None:
            record.status = status if status in {"ok", "error", "exited"} else "ok"
            record.result = result

    def _require_argv(self, message: dict[str, Any], kind: str) -> list[str]:
        argv = message.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(item, str) for item in argv):
            raise ValueError(f"{kind} requires a non-empty argv list.")
        return argv

    def _new_request_id(self) -> str:
        return secrets.token_urlsafe(12)

    def _wake(self) -> None:
        try:
            os.write(self._wakeup_w, b"x")
        except OSError:
            pass

    def _drain_wakeup_pipe(self) -> None:
        try:
            while os.read(self._wakeup_r, 4096):
                pass
        except (BlockingIOError, OSError):
            pass


def _normalize_pty_text(text: str) -> str:
    return text.replace("\r\n", "\n")


def _stderr_writer():
    try:
        return os_fd_writer(sys.stderr.fileno())
    except (OSError, ValueError, AttributeError):
        return None
