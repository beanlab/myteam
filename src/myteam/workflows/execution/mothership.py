"""Workflow supervisor: coordinates RPC, PTY sessions, workflows, and TTY switching."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from queue import Empty, Queue
import secrets
import select
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Literal

from .protocol import (
    ENV_AGENT_INPUT_JSON,
    ENV_AGENT_OUTPUT_JSON,
    ENV_AGENT_PROMPT,
    ENV_REQUEST_ID,
    ENV_SESSION_ID,
    ENV_SESSION_NONCE,
    ENV_SOCKET,
    ENV_WORKFLOW_INPUT_JSON,
    ENV_WORKFLOW_INVOCATION_ID,
    KIND_ACK_RESULT,
    KIND_POLL_RESULT,
    KIND_REPORT_RESULT,
    KIND_START_AGENT_SESSION,
    KIND_START_WORKFLOW,
    json_response,
    load_json_object,
    read_all,
    safe_unlink,
)
from .pty_process import ManagedPtyProcess
from .terminal import RealTerminal, Winsize
from ..agents.registry import DEFAULT_AGENT
from ..agents.runtime import AgentSessionContext, resolve_agent_runtime_config


@dataclass
class StartWorkflowCommand:
    request_id: str
    argv: list[str]
    parent_session_id: str | None
    cwd: str | None
    input_json: str | None


@dataclass
class StartAgentSessionCommand:
    request_id: str
    argv: list[str]
    cwd: str | None
    prompt: str
    input: dict[str, Any] | None
    output: dict[str, Any] | None
    agent: str | None
    model: str | None
    reasoning: str | None
    interactive: bool | None
    agent_session_id: str | None
    fork: bool | None
    parent_session_id: str | None
    session_nonce: str | None


@dataclass
class ReportCommand:
    request_id: str
    session_id: str
    status: str
    output: Any


@dataclass
class WorkflowCompletedCommand:
    request_id: str
    status: str
    result: Any


Command = StartWorkflowCommand | StartAgentSessionCommand | ReportCommand | WorkflowCompletedCommand


# A managed agent may spawn `myteam result` and then exit before the result
# command has finished Python startup, Fire startup, socket connection, and RPC
# handling. Do not publish an `exited` result immediately in that window, or the
# workflow caller can observe failure before the in-flight report arrives.
EXIT_REPORT_GRACE_SECONDS = float(os.environ.get("MYTEAM_EXIT_REPORT_GRACE_SECONDS", "5.0"))


@dataclass
class RequestRecord:
    request_id: str
    kind: Literal["workflow", "agent_session"]
    status: Literal["pending", "running", "ok", "error", "exited"] = "pending"
    parent_session_id: str | None = None
    session_id: str | None = None
    result: Any = None


class Mothership:
    """A deliberately small workflow supervisor and PTY multiplexer.

    The mothership owns the real terminal and the control socket for one
    workflow invocation. Workflows run as ordinary subprocesses. Calls to
    `run_agent` from those workflows are delegated back to this supervisor,
    which launches interactive agent sessions under PTYs.
    """

    def __init__(self) -> None:
        self.socket_path = ""
        self.requests: dict[str, RequestRecord] = {}
        self.results: dict[str, dict[str, Any]] = {}
        self._pending_reports: dict[str, ReportCommand] = {}
        self._pending_exits: dict[str, tuple[ManagedPtyProcess, int | None, float]] = {}
        self.active: ManagedPtyProcess | None = None
        self.stack: list[ManagedPtyProcess] = []
        self.sessions: dict[str, ManagedPtyProcess] = {}
        self.completed_sessions: dict[str, ManagedPtyProcess] = {}
        self.workflow_threads: dict[str, threading.Thread] = {}

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
        for thread in list(self.workflow_threads.values()):
            thread.join(timeout=1)
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
        """Forward the real terminal until the top-level request finishes."""

        with self._terminal as terminal:
            while not self._closed.is_set():
                self._drain_commands()
                self._reap_exited_active_session()
                self._finalize_expired_exits()

                if top_request_id in self.results:
                    return self.results[top_request_id]
                if (
                    self.active is None
                    and not self.stack
                    and self._commands.empty()
                    and not self._pending_exits
                    and not self._has_running_workflows()
                ):
                    return None

                read_fds = [self._wakeup_r]
                if self.active is not None:
                    read_fds.append(self.active.master_fd)
                if terminal.can_read_stdin and self.active is not None:
                    assert terminal.stdin_fd is not None
                    read_fds.append(terminal.stdin_fd)

                ready, _, _ = select.select(read_fds, [], [], 0.1)
                if self._wakeup_r in ready:
                    self._drain_wakeup_pipe()
                    self._drain_commands()
                    self._reap_exited_active_session()
                    self._finalize_expired_exits()
                    continue

                if self.active is not None and self.active.master_fd in ready:
                    chunk = self.active.read()
                    if chunk:
                        terminal.write_stdout(chunk)
                    else:
                        self._handle_session_exit(self.active)

                if terminal.stdin_fd is not None and terminal.stdin_fd in ready and self.active is not None:
                    data = terminal.read_stdin()
                    if data:
                        self.active.write(data)

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
                if kind == KIND_START_AGENT_SESSION:
                    response, command = self._accept_start_agent_session(message)
                    connection.sendall(json_response(**response))
                    self._commands.put(command)
                    self._wake()
                    return
                if kind == KIND_POLL_RESULT:
                    response = self._poll_result(message)
                elif kind == KIND_ACK_RESULT:
                    response = self._ack_result(message)
                elif kind == KIND_REPORT_RESULT:
                    response, command = self._accept_report_result(message)
                    connection.sendall(json_response(**response))
                    self._commands.put(command)
                    self._wake()
                    return
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

    def _accept_start_agent_session(self, message: dict[str, Any]) -> tuple[dict[str, Any], StartAgentSessionCommand]:
        argv = self._require_argv(message, KIND_START_AGENT_SESSION)
        cwd = message.get("cwd")
        if cwd is not None and not isinstance(cwd, str):
            raise ValueError("cwd must be a string or null.")
        prompt = message.get("prompt")
        if not isinstance(prompt, str) or not prompt:
            raise ValueError("start_agent_session requires prompt.")

        request_id = self._new_request_id()
        self.requests[request_id] = RequestRecord(request_id=request_id, kind="agent_session", status="pending")
        command = StartAgentSessionCommand(
            request_id=request_id,
            argv=argv,
            cwd=cwd,
            prompt=prompt,
            input=message.get("input") if isinstance(message.get("input"), dict) else None,
            output=message.get("output") if isinstance(message.get("output"), dict) else None,
            agent=message.get("agent") if isinstance(message.get("agent"), str) else None,
            model=message.get("model") if isinstance(message.get("model"), str) else None,
            reasoning=message.get("reasoning") if isinstance(message.get("reasoning"), str) else None,
            interactive=message.get("interactive") if isinstance(message.get("interactive"), bool) else None,
            agent_session_id=message.get("session_id") if isinstance(message.get("session_id"), str) else None,
            fork=message.get("fork") if isinstance(message.get("fork"), bool) else None,
            parent_session_id=message.get("parent_session_id") if isinstance(message.get("parent_session_id"), str) else None,
            session_nonce=message.get("session_nonce") if isinstance(message.get("session_nonce"), str) else None,
        )
        if command.parent_session_id is not None:
            record = self.requests[request_id]
            record.parent_session_id = command.parent_session_id
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

    def _accept_report_result(self, message: dict[str, Any]) -> tuple[dict[str, Any], ReportCommand]:
        request_id = message.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("report_result requires request_id.")
        session_id = message.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("report_result requires session_id.")
        status = message.get("status", "ok")
        if not isinstance(status, str) or not status:
            raise ValueError("status must be a string.")
        command = ReportCommand(
            request_id=request_id,
            session_id=session_id,
            status=status,
            output=message.get("output"),
        )
        session = self.sessions.get(session_id) or self.completed_sessions.get(session_id)
        if session is not None and session.request_id == request_id:
            self._pending_reports[request_id] = command
            self._pending_exits.pop(request_id, None)
            self._store_result(
                request_id,
                status=status,
                result=self._session_result_payload(session, command.output),
            )
            return {"ok": True}, command

        record = self.requests.get(request_id)
        if record is not None and record.kind == "agent_session" and record.session_id == session_id:
            self._pending_exits.pop(request_id, None)
            self._store_result(
                request_id,
                status=status,
                result=self._minimal_session_result_payload(session_id, command.output),
            )
            return {"ok": True}, command

        raise ValueError("report_result does not match a managed session.")

    def _drain_commands(self) -> None:
        while True:
            try:
                command = self._commands.get_nowait()
            except Empty:
                return
            if isinstance(command, StartWorkflowCommand):
                self._start_workflow(command)
            elif isinstance(command, StartAgentSessionCommand):
                self._start_agent_session(command)
            elif isinstance(command, WorkflowCompletedCommand):
                self._complete_workflow(command)
            else:
                self._complete_agent_session(command)

    def _start_workflow(self, command: StartWorkflowCommand) -> None:
        record = self.requests[command.request_id]
        record.status = "running"

        if command.parent_session_id is not None:
            if self.active is None or self.active.session_id != command.parent_session_id:
                self._store_result(
                    command.request_id,
                    status="error",
                    result={"message": "Parent session is not the active managed session."},
                )
                return
            self.active.suspend()
            self.stack.append(self.active)
            self.active = None
            self._terminal.clear()

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
            if completed.returncode == 0:
                status = "ok"
                result = _parse_workflow_stdout(completed.stdout)
            else:
                status = "exited"
                result = {
                    "exit_code": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                }
        except Exception as exc:
            status = "error"
            result = {"message": str(exc)}

        self._commands.put(WorkflowCompletedCommand(command.request_id, status, result))
        self._wake()

    def _start_agent_session(self, command: StartAgentSessionCommand) -> None:
        if command.parent_session_id is not None:
            if self.active is None or self.active.session_id != command.parent_session_id:
                self._store_result(
                    command.request_id,
                    status="error",
                    result={"message": "Parent session is not the active managed session."},
                )
                return
            self.active.suspend()
            self.stack.append(self.active)
            self.active = None
        elif self.active is not None:
            self._store_result(
                command.request_id,
                status="error",
                result={"message": "Another agent session is already active."},
            )
            return

        session = self._launch_agent_session(command)
        self.sessions[session.session_id] = session
        record = self.requests[command.request_id]
        record.status = "running"
        record.session_id = session.session_id
        self.active = session
        self._terminal.clear()

    def _launch_agent_session(self, command: StartAgentSessionCommand) -> ManagedPtyProcess:
        session_id = secrets.token_urlsafe(10)
        nonce = command.session_nonce or secrets.token_urlsafe(16)
        env = {
            **os.environ,
            ENV_SOCKET: self.socket_path,
            ENV_SESSION_ID: session_id,
            ENV_REQUEST_ID: command.request_id,
            ENV_SESSION_NONCE: nonce,
            ENV_AGENT_PROMPT: command.prompt,
        }
        if command.input is not None:
            env[ENV_AGENT_INPUT_JSON] = json.dumps(command.input)
        if command.output is not None:
            env[ENV_AGENT_OUTPUT_JSON] = json.dumps(command.output)

        return ManagedPtyProcess.launch(
            session_id=session_id,
            request_id=command.request_id,
            argv=command.argv,
            env=env,
            cwd=command.cwd,
            winsize=self._terminal.winsize(),
            parent_session_id=None,
            nonce=nonce,
            agent_name=command.agent,
        )

    def _complete_agent_session(self, command: ReportCommand) -> None:
        session = self.sessions.get(command.session_id)
        if session is None or session.request_id != command.request_id:
            return
        self._pending_reports.pop(command.request_id, None)
        self._pending_exits.pop(command.request_id, None)
        self._store_result(
            session.request_id,
            status=command.status,
            result=self._session_result_payload(session, command.output),
        )
        session.terminate()
        self._remove_session(session)
        record = self.requests.get(command.request_id)
        if record is not None and record.parent_session_id is not None:
            self._resume_previous_session()
        else:
            self._wake()

    def _complete_workflow(self, command: WorkflowCompletedCommand) -> None:
        self.workflow_threads.pop(command.request_id, None)
        self._store_result(command.request_id, status=command.status, result=command.result)
        record = self.requests.get(command.request_id)
        if record is not None and record.parent_session_id is not None:
            self._resume_previous_session()
        else:
            self._wake()

    def _handle_session_exit(self, session: ManagedPtyProcess) -> None:
        code = session.poll()
        if code is None:
            try:
                code = session.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                code = None
        pending_report = self._pending_reports.pop(session.request_id, None)
        if pending_report is not None:
            self._store_result(
                session.request_id,
                status=pending_report.status,
                result=self._session_result_payload(session, pending_report.output),
            )
        else:
            self._pending_exits[session.request_id] = (
                session,
                code,
                time.monotonic() + EXIT_REPORT_GRACE_SECONDS,
            )
        self._remove_session(session)
        record = self.requests.get(session.request_id)
        if record is not None and record.parent_session_id is not None:
            self._resume_previous_session()
        else:
            self._wake()

    def _reap_exited_active_session(self) -> None:
        if self.active is not None and self.active.poll() is not None:
            self._handle_session_exit(self.active)

    def _resume_previous_session(self) -> None:
        if self.stack:
            self.active = self.stack.pop()
            self.active.resume()
            self._terminal.clear()
        else:
            self.active = None
            self._wake()

    def _remove_session(self, session: ManagedPtyProcess) -> None:
        removed = self.sessions.pop(session.session_id, None)
        if removed is not None:
            self.completed_sessions[session.session_id] = removed
        if self.active is session:
            self.active = None
        session.close()

    def _finalize_expired_exits(self) -> None:
        now = time.monotonic()
        expired_request_ids = [
            request_id
            for request_id, (_session, _code, deadline) in self._pending_exits.items()
            if deadline <= now
        ]
        for request_id in expired_request_ids:
            session, code, _deadline = self._pending_exits.pop(request_id)
            if request_id in self.results:
                continue
            self._store_result(
                request_id,
                status="exited",
                result=self._session_result_payload(session, {"exit_code": code}),
            )

    def _resize_sessions(self, winsize: Winsize) -> None:
        for session in self.sessions.values():
            session.resize(winsize)

    def _store_result(self, request_id: str, *, status: str, result: Any) -> None:
        self.results[request_id] = {"status": status, "result": result}
        record = self.requests.get(request_id)
        if record is not None:
            record.status = status if status in {"ok", "error", "exited"} else "ok"
            record.result = result

    def _minimal_session_result_payload(self, session_id: str | None, output: Any) -> dict[str, Any]:
        if not isinstance(output, dict):
            output = {"value": output}
        return {
            "output": output,
            "usage": [],
            "transcript": "",
            "session_id": session_id,
            "nonce": None,
        }

    def _session_result_payload(self, session: ManagedPtyProcess, output: Any) -> dict[str, Any]:
        if not isinstance(output, dict):
            output = {"value": output}

        native_session_id = session.session_id
        usage: list[dict[str, Any]] = []
        if session.nonce:
            try:
                cwd = Path(session.cwd or os.getcwd()).resolve()
                runtime_config = resolve_agent_runtime_config(
                    session.agent_name or DEFAULT_AGENT,
                    project_root=cwd,
                    session_context=AgentSessionContext(
                        home=Path.home().resolve(),
                        project_root=cwd,
                        launch_cwd=cwd,
                    ),
                )
                native_session_id, session_path = runtime_config.get_session_info(session.nonce)
                if runtime_config.get_usage_info is not None:
                    usage_info = runtime_config.get_usage_info(session_path)
                    if usage_info is not None:
                        usage.append(asdict(usage_info))
            except Exception:
                native_session_id = session.session_id
                usage = []

        return {
            "output": output,
            "usage": usage,
            "transcript": session.recording.snapshot(),
            "session_id": native_session_id,
            "nonce": session.nonce,
        }

    def _has_running_workflows(self) -> bool:
        return any(thread.is_alive() for thread in self.workflow_threads.values())

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


def _parse_workflow_stdout(stdout: str) -> Any:
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        return None
    last_line = lines[-1]
    try:
        return json.loads(last_line)
    except json.JSONDecodeError:
        return stdout
