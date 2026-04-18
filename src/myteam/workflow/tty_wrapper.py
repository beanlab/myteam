from __future__ import annotations

from collections.abc import Callable
import errno
import fcntl
import os
import pty
import select
import shutil
import signal
import struct
import subprocess
import sys
import termios
import time

from .models import PtyRunResult


def _terminal_size() -> tuple[int, int]:
    size = shutil.get_terminal_size(fallback=(80, 24))
    return size.lines, size.columns


def _set_pty_window_size(fd: int) -> None:
    rows, columns = _terminal_size()
    winsize = struct.pack("HHHH", rows, columns, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


def _decode_transcript(chunks: list[bytes]) -> str:
    return b"".join(chunks).decode("utf-8", errors="replace")


def _write_all(master_fd: int, text: str) -> None:
    pending = text.encode("utf-8")
    while pending:
        _, writable, _ = select.select([], [master_fd], [], 0.1)
        if master_fd not in writable:
            continue
        try:
            written = os.write(master_fd, pending)
        except OSError as exc:
            if exc.errno in {errno.EIO, errno.EBADF}:
                return
            raise
        pending = pending[written:]


def run_pty_session(
    argv: list[str],
    initial_input: str | None,
    on_output: Callable[[bytes], str | None],
    *,
    inactivity_timeout_seconds: int = 300,
    graceful_shutdown_timeout_seconds: int = 30,
) -> PtyRunResult:
    """Run a PTY session where callback-returned text is written back as child input."""
    master_fd, slave_fd = pty.openpty()
    _set_pty_window_size(slave_fd)
    os.set_blocking(master_fd, False)

    previous_sigwinch_handler = None
    child_process: subprocess.Popen[bytes] | None = None
    transcript_chunks: list[bytes] = []
    shutdown_requested_at: float | None = None
    last_output_at = time.monotonic()

    def _handle_sigwinch(signum: int, frame: object) -> None:
        del signum, frame
        _set_pty_window_size(slave_fd)

    try:
        previous_sigwinch_handler = signal.getsignal(signal.SIGWINCH)
        signal.signal(signal.SIGWINCH, _handle_sigwinch)

        child_process = subprocess.Popen(
            argv,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=os.getcwd(),
            env=os.environ.copy(),
            close_fds=True,
        )
    finally:
        os.close(slave_fd)

    try:
        if initial_input is not None:
            _write_all(master_fd, initial_input)

        while True:
            if child_process.poll() is not None:
                while True:
                    try:
                        chunk = os.read(master_fd, 4096)
                    except OSError as exc:
                        if exc.errno in {errno.EIO, errno.EBADF}:
                            break
                        raise
                    if not chunk:
                        break
                    transcript_chunks.append(chunk)
                    last_output_at = time.monotonic()
                    callback_input = on_output(chunk)
                    if callback_input is not None:
                        _write_all(master_fd, callback_input)
                        if shutdown_requested_at is None:
                            shutdown_requested_at = time.monotonic()
                break

            now = time.monotonic()
            if now - last_output_at > inactivity_timeout_seconds:
                child_process.terminate()
                raise TimeoutError(
                    f"PTY session exceeded inactivity timeout of {inactivity_timeout_seconds} seconds."
                )

            if (
                shutdown_requested_at is not None
                and now - shutdown_requested_at > graceful_shutdown_timeout_seconds
            ):
                child_process.terminate()
                child_process.wait(timeout=5)
                raise TimeoutError(
                    "PTY session did not exit before graceful shutdown timeout expired."
                )

            readable, _, _ = select.select([master_fd], [], [], 0.1)
            if master_fd not in readable:
                continue

            try:
                chunk = os.read(master_fd, 4096)
            except OSError as exc:
                if exc.errno == errno.EIO:
                    continue
                raise

            if not chunk:
                continue

            transcript_chunks.append(chunk)
            last_output_at = time.monotonic()
            callback_input = on_output(chunk)
            if callback_input is not None:
                _write_all(master_fd, callback_input)
                if shutdown_requested_at is None:
                    shutdown_requested_at = time.monotonic()

        exit_code = child_process.wait()
        return PtyRunResult(exit_code=exit_code, transcript=_decode_transcript(transcript_chunks))
    finally:
        if child_process is not None and child_process.poll() is None:
            child_process.kill()
            child_process.wait(timeout=5)
        os.close(master_fd)
        if previous_sigwinch_handler is not None:
            signal.signal(signal.SIGWINCH, previous_sigwinch_handler)
