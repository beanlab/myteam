"""Workflow PTY process stack management."""
from __future__ import annotations

import os
from typing import Any

from .protocol import ENV_SOCKET, ENV_WORKFLOW_INPUT_JSON, ENV_WORKFLOW_INVOCATION_ID
from .pty_process import ManagedPtyProcess
from .terminal import RealTerminal, Winsize
from .workflow_commands import StartWorkflowCommand


class WorkflowStartError(Exception):
    """Raised when a workflow cannot be started by the supervisor."""

    def __init__(self, result_payload: dict[str, Any]) -> None:
        super().__init__(str(result_payload.get("error_text") or "Workflow start failed."))
        self.result_payload = result_payload


class WorkflowStack:
    """Owns active, suspended, and known workflow PTY sessions."""

    def __init__(self, terminal: RealTerminal) -> None:
        self.terminal = terminal
        self.active: ManagedPtyProcess | None = None
        self.stack: list[ManagedPtyProcess] = []
        self.sessions: dict[str, ManagedPtyProcess] = {}

    def start(self, command: StartWorkflowCommand, *, socket_path: str) -> ManagedPtyProcess:
        self._prepare_for_start(command)
        session = self._launch(command, socket_path=socket_path)
        self.sessions[session.session_id] = session
        self.active = session
        self.terminal.flush_input()
        return session

    def resume_previous(self) -> bool:
        if self.stack:
            self.terminal.flush_input()
            self._scroll_current_view_offscreen()
            self.active = self.stack.pop()
            self.active.resume()
            self.terminal.flush_input()
            return True
        self.active = None
        return False

    def _scroll_current_view_offscreen(self):
        if not self.terminal.can_display_live_output:
            return
        rows, _ = self.terminal.winsize()
        self.terminal.write_stdout(b"\r\n" * rows)

    def remove(self, session: ManagedPtyProcess):
        self.sessions.pop(session.session_id, None)
        if self.active is session:
            self.active = None
        session.close()

    def resize(self, winsize: Winsize):
        for session in self.sessions.values():
            session.resize(winsize)

    def close_all(self):
        for session in list(self.sessions.values()):
            session.terminate()
            session.close()

    def _prepare_for_start(self, command: StartWorkflowCommand):
        if command.parent_session_id is not None:
            self._suspend_parent(command.parent_session_id)
            return
        if self.active is not None:
            raise WorkflowStartError(
                {
                    "exit_code": 1,
                    "result_text": "",
                    "error_text": "Another workflow is already active.\n",
                }
            )

    def _suspend_parent(self, parent_session_id: str):
        if self.active is None or self.active.session_id != parent_session_id:
            raise WorkflowStartError(
                {
                    "exit_code": 1,
                    "result_text": "",
                    "error_text": "Parent workflow is not the active managed workflow.\n",
                }
            )
        self.terminal.flush_input()
        self.active.suspend()
        self.stack.append(self.active)
        self.active = None
        self.terminal.flush_input()

    def _launch(self, command: StartWorkflowCommand, *, socket_path: str) -> ManagedPtyProcess:
        env = {
            **os.environ,
            ENV_SOCKET: socket_path,
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
            winsize=self.terminal.winsize(),
            parent_session_id=command.parent_session_id,
            merge_stderr=False,
        )
