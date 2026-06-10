"""Prototype mothership: coordinates RPC, PTY sessions, and TTY switching."""
from __future__ import annotations

from dataclasses import dataclass
import os
from queue import Empty, Queue
import secrets
import select
import socket
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any

from .protocol import ENV_SESSION_ID, ENV_SOCKET, json_response, load_json_object, read_all, safe_unlink
from .pty_process import ManagedPtyProcess
from .terminal import RealTerminal, Winsize


@dataclass
class StartCommand:
    request_id: str
    argv: list[str]
    parent_session_id: str | None
    cwd: str | None
    input_json: str | None


@dataclass
class ReportCommand:
    session_id: str
    status: str
    result: Any


class Mothership:
    """A deliberately small PTY multiplexer for nested `myteam start` calls.

    The mothership owns the real terminal and the RPC socket. Individual child
    commands are represented by `ManagedPtyProcess`; terminal raw-mode handling
    is isolated in `RealTerminal`.
    """

    def __init__(self) -> None:
        self.socket_path = ""
        self.results: dict[str, dict[str, Any]] = {}
        self.active: ManagedPtyProcess | None = None
        self.stack: list[ManagedPtyProcess] = []
        self.sessions: dict[str, ManagedPtyProcess] = {}

        self._tmpdir: tempfile.TemporaryDirectory[str] | None = None
        self._server: socket.socket | None = None
        self._server_thread: threading.Thread | None = None
        self._closed = threading.Event()
        self._commands: Queue[StartCommand | ReportCommand] = Queue()
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

    def run_until_complete(self, top_request_id: str) -> dict[str, Any] | None:
        """Forward the real terminal until the top-level request finishes."""

        with self._terminal as terminal:
            while not self._closed.is_set():
                self._drain_commands()
                self._reap_exited_active_session()

                if top_request_id in self.results:
                    return self.results[top_request_id]
                if self.active is None and not self.stack and self._commands.empty():
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
                if kind == "start_session":
                    response, command = self._accept_start_session(message)
                    connection.sendall(json_response(**response))
                    self._commands.put(command)
                    self._wake()
                    return
                if kind == "poll_result":
                    response = self._poll_result(message)
                elif kind == "report_result":
                    response, command = self._accept_report_result(message)
                    connection.sendall(json_response(**response))
                    self._commands.put(command)
                    self._wake()
                    return
                else:
                    response = {"ok": False, "error": f"Unsupported RPC kind: {kind!r}"}
            except Exception as exc:  # prototype: return friendly errors over the socket
                response = {"ok": False, "error": str(exc)}
            try:
                connection.sendall(json_response(**response))
            except OSError:
                pass

    def _accept_start_session(self, message: dict[str, Any]) -> tuple[dict[str, Any], StartCommand]:
        argv = message.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(item, str) for item in argv):
            raise ValueError("start_session requires a non-empty argv list.")
        parent_session_id = message.get("parent_session_id")
        if parent_session_id is not None and not isinstance(parent_session_id, str):
            raise ValueError("parent_session_id must be a string or null.")
        cwd = message.get("cwd")
        if cwd is not None and not isinstance(cwd, str):
            raise ValueError("cwd must be a string or null.")
        input_json = message.get("input_json")
        if input_json is not None and not isinstance(input_json, str):
            raise ValueError("input_json must be a string or null.")

        request_id = secrets.token_urlsafe(12)
        command = StartCommand(
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

    def _accept_report_result(self, message: dict[str, Any]) -> tuple[dict[str, Any], ReportCommand]:
        session_id = message.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("report_result requires session_id.")
        status = message.get("status", "ok")
        if not isinstance(status, str) or not status:
            raise ValueError("status must be a string.")
        return {"ok": True}, ReportCommand(session_id=session_id, status=status, result=message.get("result"))

    def _drain_commands(self) -> None:
        while True:
            try:
                command = self._commands.get_nowait()
            except Empty:
                return
            if isinstance(command, StartCommand):
                self._start_session(command)
            else:
                self._complete_session(command)

    def _start_session(self, command: StartCommand) -> None:
        if self.active is not None:
            self.active.suspend()
            self.stack.append(self.active)

        session = self._launch_session(command)
        self.sessions[session.session_id] = session
        self.active = session
        self._terminal.clear()

    def _launch_session(self, command: StartCommand) -> ManagedPtyProcess:
        session_id = secrets.token_urlsafe(10)
        env = {
            **os.environ,
            ENV_SOCKET: self.socket_path,
            ENV_SESSION_ID: session_id,
        }
        if command.input_json is not None:
            env["MYTEAM_WORKFLOW_INPUT_JSON"] = command.input_json

        return ManagedPtyProcess.launch(
            session_id=session_id,
            request_id=command.request_id,
            argv=command.argv,
            env=env,
            cwd=command.cwd,
            winsize=self._terminal.winsize(),
            parent_session_id=command.parent_session_id,
        )

    def _complete_session(self, command: ReportCommand) -> None:
        session = self.sessions.get(command.session_id)
        if session is None:
            return
        self.results[session.request_id] = {"status": command.status, "result": command.result}
        session.terminate()
        self._remove_session(session)
        self._resume_previous_session()

    def _handle_session_exit(self, session: ManagedPtyProcess) -> None:
        code = session.poll()
        if code is None:
            try:
                code = session.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                code = None
        self.results.setdefault(
            session.request_id,
            {"status": "exited", "result": {"exit_code": code}},
        )
        self._remove_session(session)
        self._resume_previous_session()

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
        self.sessions.pop(session.session_id, None)
        if self.active is session:
            self.active = None
        session.close()

    def _resize_sessions(self, winsize: Winsize) -> None:
        for session in self.sessions.values():
            session.resize(winsize)

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
