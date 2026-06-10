"""Managed child PTY process for the workflow supervisor."""
from __future__ import annotations

from dataclasses import dataclass, field
import errno
import fcntl
import os
import pty
import signal
import subprocess
import termios
from collections.abc import Mapping

from .recording import TerminalRecording
from .terminal import Winsize


@dataclass
class ManagedPtyProcess:
    """One child command attached to one PTY."""

    session_id: str
    request_id: str
    argv: list[str]
    master_fd: int
    process: subprocess.Popen[bytes]
    parent_session_id: str | None = None
    nonce: str | None = None
    agent_name: str | None = None
    cwd: str | None = None
    recording: TerminalRecording = field(default_factory=TerminalRecording)

    @classmethod
    def launch(
        cls,
        *,
        session_id: str,
        request_id: str,
        argv: list[str],
        env: Mapping[str, str],
        cwd: str | None,
        winsize: Winsize,
        parent_session_id: str | None = None,
        nonce: str | None = None,
        agent_name: str | None = None,
    ) -> "ManagedPtyProcess":
        master_fd, slave_fd = pty.openpty()
        set_winsize(master_fd, winsize)
        try:
            process = subprocess.Popen(
                argv,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=cwd,
                env=dict(env),
                preexec_fn=_make_controlling_terminal_preexec(slave_fd),
                close_fds=True,
            )
        finally:
            os.close(slave_fd)

        return cls(
            session_id=session_id,
            request_id=request_id,
            argv=argv,
            master_fd=master_fd,
            process=process,
            parent_session_id=parent_session_id,
            nonce=nonce,
            agent_name=agent_name,
            cwd=cwd,
        )

    def poll(self) -> int | None:
        return self.process.poll()

    def wait(self, timeout: float | None = None) -> int:
        return self.process.wait(timeout=timeout)

    def read(self, size: int = 4096) -> bytes:
        try:
            chunk = os.read(self.master_fd, size)
        except OSError as exc:
            if exc.errno == errno.EIO:
                return b""
            raise
        self.recording.feed(chunk)
        return chunk

    def write(self, data: bytes) -> None:
        view = memoryview(data)
        while view:
            written = os.write(self.master_fd, view)
            view = view[written:]

    def resize(self, winsize: Winsize) -> None:
        set_winsize(self.master_fd, winsize)

    def foreground_pgrp(self) -> int:
        try:
            return os.tcgetpgrp(self.master_fd)
        except OSError:
            return self.process.pid

    def suspend(self) -> None:
        try:
            self._signal_process_group(signal.SIGSTOP)
        except OSError:
            pass

    def resume(self) -> None:
        try:
            self._signal_process_group(signal.SIGCONT)
        except OSError:
            pass

    def terminate(self, *, timeout: float = 0.5) -> None:
        if self.process.poll() is not None:
            return
        try:
            self._signal_process_group(signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                self._signal_process_group(signal.SIGKILL)
            except OSError:
                self.process.kill()

    def close(self) -> None:
        try:
            os.close(self.master_fd)
        except OSError:
            pass

    def _signal_process_group(self, signum: signal.Signals) -> None:
        os.killpg(self.foreground_pgrp(), signum)


def set_winsize(master_fd: int, winsize: Winsize) -> None:
    try:
        termios.tcsetwinsize(master_fd, winsize)
    except OSError:
        pass


def _make_controlling_terminal_preexec(slave_fd: int):
    def preexec() -> None:
        os.setsid()
        fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)

    return preexec
