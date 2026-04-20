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
import tty

from .models import PtyRunResult

_DEBUG_ENV_VAR = "MYTEAM_WORKFLOW_DEBUG"


def _terminal_size() -> tuple[int, int]:
    size = shutil.get_terminal_size(fallback=(80, 24))
    return size.lines, size.columns


def _set_pty_window_size(fd: int) -> None:
    rows, columns = _terminal_size()
    winsize = struct.pack("HHHH", rows, columns, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


def _decode_transcript(chunks: list[bytes]) -> str:
    return b"".join(chunks).decode("utf-8", errors="replace")


def _debug_enabled() -> bool:
    return os.environ.get(_DEBUG_ENV_VAR) == "1"


def _debug_log(message: str) -> None:
    if _debug_enabled():
        print(f"[workflow-debug] {message}", file=sys.stderr)


def _debug_echo(chunk: bytes) -> None:
    if not _debug_enabled():
        return
    try:
        sys.stderr.buffer.write(chunk)
        sys.stderr.buffer.flush()
    except Exception:
        return


def _has_interactive_parent_terminal() -> bool:
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
        return False


def _parent_terminal_fds() -> tuple[int, int]:
    return sys.stdin.fileno(), sys.stdout.fileno()


def _echo_to_parent_stdout(chunk: bytes) -> None:
    try:
        sys.stdout.buffer.write(chunk)
        sys.stdout.buffer.flush()
        return
    except Exception:
        pass

    stdout_fd = None
    try:
        _, stdout_fd = _parent_terminal_fds()
        os.write(stdout_fd, chunk)
    except Exception:
        return


def _write_all(
    master_fd: int,
    text: str,
    *,
    chunk_size: int | None = None,
    inter_chunk_delay_seconds: float = 0.0,
) -> None:
    _debug_log(f"write {len(text.encode('utf-8'))} bytes")
    pending = text.encode("utf-8")
    while pending:
        _, writable, _ = select.select([], [master_fd], [], 0.1)
        if master_fd not in writable:
            continue
        current_chunk = pending if not chunk_size else pending[:chunk_size]
        try:
            written = os.write(master_fd, current_chunk)
        except OSError as exc:
            if exc.errno in {errno.EIO, errno.EBADF}:
                return
            raise
        pending = pending[written:]
        if inter_chunk_delay_seconds > 0 and pending:
            time.sleep(inter_chunk_delay_seconds)


def _write_initial_input(master_fd: int, text: str) -> None:
    _write_all(master_fd, text)


def _type_callback_input(master_fd: int, text: str) -> None:
    _write_all(
        master_fd,
        text,
        chunk_size=1,
        inter_chunk_delay_seconds=0.01,
    )


def run_pty_session(
    argv: list[str],
    initial_input: str | None,
    on_output: Callable[[bytes], str | None],
    *,
    inactivity_timeout_seconds: int = 300,
    graceful_shutdown_timeout_seconds: int = 30,
) -> PtyRunResult:
    """Run a PTY session where callback-returned text is written back as child input."""
    initial_input_sent = initial_input is None
    started_at = time.monotonic()
    _debug_log(f"launch argv={argv!r}")
    master_fd, slave_fd = pty.openpty()
    _set_pty_window_size(slave_fd)
    os.set_blocking(master_fd, False)

    previous_sigwinch_handler = None
    child_process: subprocess.Popen[bytes] | None = None
    transcript_chunks: list[bytes] = []
    shutdown_requested_at: float | None = None
    last_output_at = time.monotonic()
    interactive_passthrough = initial_input is None and _has_interactive_parent_terminal()
    parent_stdin_fd: int | None = None
    previous_parent_term_settings: list[int] | None = None
    master_fd_open = True

    def _handle_sigwinch(signum: int, frame: object) -> None:
        del signum, frame
        _set_pty_window_size(slave_fd)

    try:
        previous_sigwinch_handler = signal.getsignal(signal.SIGWINCH)
        signal.signal(signal.SIGWINCH, _handle_sigwinch)
        if interactive_passthrough:
            parent_stdin_fd, _ = _parent_terminal_fds()
            previous_parent_term_settings = termios.tcgetattr(parent_stdin_fd)
            tty.setraw(parent_stdin_fd)

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
                    if interactive_passthrough:
                        _echo_to_parent_stdout(chunk)
                    _debug_echo(chunk)
                    last_output_at = time.monotonic()
                    callback_input = on_output(chunk)
                    if callback_input is not None:
                        _type_callback_input(master_fd, callback_input)
                        if shutdown_requested_at is None:
                            shutdown_requested_at = time.monotonic()
                break

            now = time.monotonic()
            if (
                not initial_input_sent
                and initial_input is not None
                and now - started_at >= 0.2
            ):
                _debug_log("sending initial input after startup delay")
                _write_initial_input(master_fd, initial_input)
                initial_input_sent = True

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

            read_fds: list[int] = []
            if master_fd_open:
                read_fds.append(master_fd)
            if interactive_passthrough and parent_stdin_fd is not None:
                read_fds.append(parent_stdin_fd)

            if not read_fds:
                time.sleep(0.1)
                continue

            readable, _, _ = select.select(read_fds, [], [], 0.1)

            if interactive_passthrough and parent_stdin_fd in readable:
                try:
                    parent_input = os.read(parent_stdin_fd, 4096)
                except OSError as exc:
                    if exc.errno not in {errno.EIO, errno.EBADF}:
                        raise
                    parent_input = b""

                if not parent_input:
                    shutdown_requested_at = shutdown_requested_at or time.monotonic()
                    try:
                        os.close(master_fd)
                    except OSError:
                        pass
                    master_fd_open = False
                    continue

                try:
                    os.write(master_fd, parent_input)
                except OSError as exc:
                    if exc.errno in {errno.EIO, errno.EBADF}:
                        shutdown_requested_at = shutdown_requested_at or time.monotonic()
                        master_fd_open = False
                        continue
                    raise

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
            if interactive_passthrough:
                _echo_to_parent_stdout(chunk)
            _debug_echo(chunk)
            _debug_log(f"read {len(chunk)} bytes")
            last_output_at = time.monotonic()
            if not initial_input_sent and initial_input is not None:
                _debug_log("sending initial input after first output")
                _write_initial_input(master_fd, initial_input)
                initial_input_sent = True
            callback_input = on_output(chunk)
            if callback_input is not None:
                _debug_log("callback requested input write")
                _type_callback_input(master_fd, callback_input)
                if shutdown_requested_at is None:
                    shutdown_requested_at = time.monotonic()

        exit_code = child_process.wait()
        return PtyRunResult(exit_code=exit_code, transcript=_decode_transcript(transcript_chunks))
    finally:
        if child_process is not None and child_process.poll() is None:
            child_process.kill()
            child_process.wait(timeout=5)
        try:
            os.close(master_fd)
        except OSError:
            pass
        if previous_parent_term_settings is not None and parent_stdin_fd is not None:
            termios.tcsetattr(parent_stdin_fd, termios.TCSADRAIN, previous_parent_term_settings)
        if previous_sigwinch_handler is not None:
            signal.signal(signal.SIGWINCH, previous_sigwinch_handler)
