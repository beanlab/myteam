"""Shared PTY forwarding utilities for workflows and agent sessions."""
from __future__ import annotations

from dataclasses import dataclass, field
import codecs
import os
import select
import time
from collections.abc import Callable, Iterable
from typing import Any

from .pty_process import ManagedPtyProcess
from .terminal import RealTerminal


BytesWriter = Callable[[bytes], None]


@dataclass(frozen=True)
class PtyPumpResult:
    """Result from one PTY forwarding iteration."""

    stdout_eof: bool = False
    stdout_bytes: int = 0
    stderr_bytes: int = 0
    stdin_bytes: int = 0
    ready_extra_fds: set[int] = field(default_factory=set)


class TextStreamBinaryAdapter:
    """Binary-looking writer for text streams without a ``buffer`` attribute."""

    def __init__(self, stream: Any) -> None:
        self.stream = stream
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

    def write(self, data: bytes) -> None:
        self.stream.write(self._decoder.decode(data))

    def flush(self) -> None:
        self.stream.flush()


def binary_output_stream(stream: Any) -> Any:
    return stream.buffer if hasattr(stream, "buffer") else TextStreamBinaryAdapter(stream)


def write_bytes(writer: Any, chunk: bytes) -> None:
    if not chunk:
        return
    try:
        writer.write(chunk)
        writer.flush()
    except Exception:
        pass


def os_fd_writer(fd: int) -> BytesWriter:
    def _write(data: bytes) -> None:
        if not data:
            return
        try:
            os.write(fd, data)
        except OSError:
            pass

    return _write


def pump_pty_once(
    session: ManagedPtyProcess,
    terminal: RealTerminal,
    *,
    timeout: float,
    stdout_writer: BytesWriter | None = None,
    stderr_writer: BytesWriter | None = None,
    forward_stdout: bool = True,
    forward_stderr: bool = True,
    forward_stdin: bool = True,
    extra_fds: Iterable[int] = (),
    preempt_on_extra_fd: bool = False,
) -> PtyPumpResult:
    """Forward one select cycle between ``terminal`` and ``session``.

    Bytes read from the PTY are recorded by ``ManagedPtyProcess.read()`` /
    ``read_stderr()`` and forwarded to the provided writers when requested.
    """

    stderr_fd = session.stderr_fd()
    stdin_fd = terminal.stdin_fd if forward_stdin and terminal.can_read_stdin else None
    extra = tuple(fd for fd in extra_fds if fd >= 0)

    read_fds = _unique_fds([
        session.master_fd,
        *([stderr_fd] if stderr_fd is not None else []),
        *([stdin_fd] if stdin_fd is not None else []),
        *extra,
    ])
    ready, _, _ = select.select(read_fds, [], [], timeout)
    ready_set = set(ready)
    ready_extra_fds = {fd for fd in extra if fd in ready_set}

    if preempt_on_extra_fd and ready_extra_fds:
        return PtyPumpResult(ready_extra_fds=ready_extra_fds)

    stdout_eof = False
    stdout_bytes = 0
    stderr_bytes = 0
    stdin_bytes = 0

    if session.master_fd in ready_set:
        chunk = session.read()
        if chunk:
            stdout_bytes = len(chunk)
            if forward_stdout and stdout_writer is not None:
                stdout_writer(chunk)
        else:
            stdout_eof = True

    if stderr_fd is not None and stderr_fd in ready_set:
        chunk = session.read_stderr()
        if chunk:
            stderr_bytes = len(chunk)
            if forward_stderr and stderr_writer is not None:
                stderr_writer(chunk)

    if stdin_fd is not None and stdin_fd in ready_set:
        data = terminal.read_stdin()
        if data:
            stdin_bytes = len(data)
            try:
                session.write(data)
            except OSError:
                pass

    return PtyPumpResult(
        stdout_eof=stdout_eof,
        stdout_bytes=stdout_bytes,
        stderr_bytes=stderr_bytes,
        stdin_bytes=stdin_bytes,
        ready_extra_fds=ready_extra_fds,
    )


def drain_pty_output(
    session: ManagedPtyProcess,
    *,
    stdout_writer: BytesWriter | None = None,
    stderr_writer: BytesWriter | None = None,
    forward_stdout: bool = True,
    forward_stderr: bool = True,
    quiet_timeout: float = 0.05,
    max_timeout: float = 0.5,
) -> None:
    """Drain PTY output until EOF or a short quiet period.

    A zero-timeout select can miss bytes that arrive immediately after process
    exit. This bounded quiet drain is used by both the workflow supervisor and
    ``run_agent`` so final output is not lost.
    """

    stdout_open = True
    stderr_open = session.stderr_fd() is not None
    deadline = time.monotonic() + max_timeout
    quiet_deadline = time.monotonic() + quiet_timeout

    while (stdout_open or stderr_open) and time.monotonic() < deadline:
        stderr_fd = session.stderr_fd() if stderr_open else None
        fds = _unique_fds([
            *([session.master_fd] if stdout_open else []),
            *([stderr_fd] if stderr_fd is not None else []),
        ])
        if not fds:
            return

        timeout = max(0.0, min(deadline, quiet_deadline) - time.monotonic())
        try:
            ready, _, _ = select.select(fds, [], [], timeout)
        except OSError:
            return
        if not ready:
            return

        made_progress = False
        ready_set = set(ready)
        if stdout_open and session.master_fd in ready_set:
            chunk = session.read()
            if chunk:
                made_progress = True
                if forward_stdout and stdout_writer is not None:
                    stdout_writer(chunk)
            else:
                stdout_open = False

        if stderr_fd is not None and stderr_fd in ready_set:
            chunk = session.read_stderr()
            if chunk:
                made_progress = True
                if forward_stderr and stderr_writer is not None:
                    stderr_writer(chunk)
            else:
                stderr_open = False

        if made_progress:
            quiet_deadline = time.monotonic() + quiet_timeout


def _unique_fds(fds: Iterable[int | None]) -> list[int]:
    seen: set[int] = set()
    unique: list[int] = []
    for fd in fds:
        if fd is None or fd < 0 or fd in seen:
            continue
        seen.add(fd)
        unique.append(fd)
    return unique
