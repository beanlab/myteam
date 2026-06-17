"""Workflow supervisor: coordinates workflow RPC requests and PTY handoff.

This module is workflow-only. Agent sessions are owned by `run_agent` in
`myteam.workflows.agent_session` and report results over the per-agent result
channel, not through this supervisor.
"""
from __future__ import annotations

import os
from queue import Empty, Queue
import select
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

from .live_output import LiveOutputTracker
from .protocol import safe_unlink
from .pty_forwarding import drain_pty_output, pump_pty_once
from .pty_process import ManagedPtyProcess
from .terminal import RealTerminal, Winsize
from .workflow_commands import Command, StartWorkflowCommand
from .workflow_rpc import WorkflowRpcServer
from .workflow_stack import WorkflowStack, WorkflowStartError
from .workflow_store import WorkflowStore


class Supervisor:
    """Small workflow supervisor and nested `myteam start` RPC server.

    Workflows are launched under PTYs. The supervisor owns the user's real
    terminal and forwards input/output to one active workflow at a time. Nested
    `myteam start` requests suspend the active workflow process group, run the
    child workflow, store the child process result, and then resume the parent.
    """

    def __init__(self) -> None:
        self.socket_path = ""
        self.store = WorkflowStore()
        self._tmpdir: tempfile.TemporaryDirectory[str] | None = None
        self._rpc_server: WorkflowRpcServer | None = None
        self._closed = threading.Event()
        self._commands: Queue[Command] = Queue()
        self._wakeup_r = -1
        self._wakeup_w = -1
        self._terminal = RealTerminal(on_resize=self._resize_sessions)
        self._stack = WorkflowStack(self._terminal)
        self._live_output = LiveOutputTracker()

    def __enter__(self) -> "Supervisor":
        self._tmpdir = tempfile.TemporaryDirectory(prefix="myteam-supervisor-")
        self.socket_path = str(Path(self._tmpdir.name) / "supervisor.sock")
        self._wakeup_r, self._wakeup_w = os.pipe()
        os.set_blocking(self._wakeup_r, False)

        self._rpc_server = WorkflowRpcServer(
            socket_path=self.socket_path,
            store=self.store,
            commands=self._commands,
            wake=self._wake,
            closed=self._closed,
        )
        self._rpc_server.start()
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        self._terminal.flush_input()
        self._terminal.restore()
        self._closed.set()
        if self._rpc_server is not None:
            self._rpc_server.close()
        self._stack.close_all()
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
        request_id = self.store.create_request().request_id
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

                result = self.store.get_result(top_request_id)
                if result is not None:
                    self._live_output.finish(terminal, enabled=live_forwarding)
                    return result
                if self._stack.active is None and not self._stack.stack and self._commands.empty():
                    return None

                if self._stack.active is None:
                    ready, _, _ = select.select([self._wakeup_r], [], [], 0.1)
                    if self._wakeup_r in ready:
                        self._drain_wakeup_pipe()
                    continue

                stdout_writer = self._live_output.stdout_writer(terminal, enabled=live_forwarding)
                stderr_writer = self._live_output.stderr_writer(enabled=live_forwarding)
                activity = pump_pty_once(
                    self._stack.active,
                    terminal,
                    timeout=0.1,
                    stdout_writer=stdout_writer,
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
                        self._stack.active,
                        stdout_writer=stdout_writer,
                        stderr_writer=stderr_writer,
                        forward_stdout=live_forwarding,
                        forward_stderr=live_forwarding,
                    )
                    continue

        return None

    def _drain_commands(self) -> None:
        while True:
            try:
                command = self._commands.get_nowait()
            except Empty:
                return
            self._start_workflow(command)

    def _start_workflow(self, command: StartWorkflowCommand) -> None:
        self.store.mark_running(command.request_id)
        try:
            self._stack.start(command, socket_path=self.socket_path)
        except WorkflowStartError as exc:
            self.store.store_result(command.request_id, status="error", result=exc.result_payload)

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
        parent_session_id = self.store.complete_exit_request(
            session.request_id,
            exit_code=exit_code,
            transcript=_normalize_pty_text(session.recording.snapshot()),
            stderr_transcript=session.stderr_snapshot(),
        )
        self._stack.remove(session)
        self._finish_completed_request(parent_session_id)

    def _finish_completed_request(self, parent_session_id: str | None) -> None:
        if parent_session_id is not None:
            if not self._stack.resume_previous():
                self._wake()
        else:
            self._wake()

    def _reap_exited_active_session(self, *, terminal: RealTerminal, live_forwarding: bool) -> None:
        if self._stack.active is not None and self._stack.active.poll() is not None:
            self._handle_workflow_exit(
                self._stack.active,
                stdout_writer=self._live_output.stdout_writer(terminal, enabled=live_forwarding),
                stderr_writer=self._live_output.stderr_writer(enabled=live_forwarding),
                forward_stdout=live_forwarding,
                forward_stderr=live_forwarding,
            )

    def _resize_sessions(self, winsize: Winsize) -> None:
        self._stack.resize(winsize)

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

