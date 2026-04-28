from __future__ import annotations

from collections.abc import Callable
import os
import pty
import select
import shutil
import signal
import subprocess
import sys
import termios
import time
import tty
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from myteam.workflow.models import PtyRunResult
else:
    from .models import PtyRunResult


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
    process: subprocess.Popen[bytes] | None = None
    stdin_fd: int | None = None
    restore_tty: list[int] | None = None
    previous_winch_handler = None
    transcript_chunks: list[bytes] = []
    graceful_shutdown_started_at: float | None = None
    parent_stdin_closed = False
    # Interactive TUIs may echo or mishandle input written before their terminal is initialized.
    pending_initial_input = initial_input
    # Codex accepts "/quit" when the text lands in the input box and Enter arrives
    # as a later keystroke. If we send both too quickly, its paste-burst logic
    # groups them together and the command stays in the composer instead of executing.
    injected_enter_delay_seconds = 0.02

    def write_injected_input(text: str) -> None:
        payload = text
        if payload.endswith("\r\n"):
            payload = payload[:-2]
        elif payload.endswith("\n") or payload.endswith("\r"):
            payload = payload[:-1]

        if payload:
            os.write(master_fd, payload.encode("utf-8"))
            time.sleep(injected_enter_delay_seconds)
        os.write(master_fd, b"\r")

    def copy_terminal_size() -> None:
        size = shutil.get_terminal_size(fallback=(80, 24))
        packed = termios.tcgetwinsize(sys.stdin.fileno()) if sys.stdin.isatty() else (size.lines, size.columns)
        termios.tcsetwinsize(master_fd, packed)

    def handle_winch(_signum: int, _frame: object) -> None:
        try:
            copy_terminal_size()
        except OSError:
            pass

    try:
        copy_terminal_size()
        process = subprocess.Popen(
            argv,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            start_new_session=True,
            close_fds=True,
        )
        os.close(slave_fd)
        slave_fd = -1

        if sys.stdin.isatty():
            stdin_fd = sys.stdin.fileno()
            restore_tty = termios.tcgetattr(stdin_fd)
            tty.setraw(stdin_fd)

        previous_winch_handler = signal.getsignal(signal.SIGWINCH)
        signal.signal(signal.SIGWINCH, handle_winch)

        last_output_at = time.monotonic()
        while True:
            if process.poll() is not None:
                break

            now = time.monotonic()
            if graceful_shutdown_started_at is not None:
                timeout = max(0.0, graceful_shutdown_timeout_seconds - (now - graceful_shutdown_started_at))
            else:
                timeout = max(0.0, inactivity_timeout_seconds - (now - last_output_at))

            read_fds = [master_fd]
            if stdin_fd is not None and not parent_stdin_closed:
                read_fds.append(stdin_fd)

            ready, _, _ = select.select(read_fds, [], [], timeout)
            if not ready:
                if graceful_shutdown_started_at is not None:
                    process.terminate()
                    graceful_shutdown_started_at = time.monotonic()
                    grace_ready, _, _ = select.select([master_fd], [], [], 1.0)
                    if not grace_ready and process.poll() is None:
                        process.kill()
                    continue
                raise TimeoutError(
                    f"PTY session became inactive for {inactivity_timeout_seconds} seconds."
                )

            if master_fd in ready:
                try:
                    chunk = os.read(master_fd, 4096)
                except OSError:
                    chunk = b""

                if not chunk:
                    break

                transcript_chunks.append(chunk)
                last_output_at = time.monotonic()
                os.write(sys.stdout.fileno(), chunk)
                injected = on_output(chunk)
                if pending_initial_input is not None:
                    write_injected_input(pending_initial_input)
                    pending_initial_input = None
                if injected is not None:
                    write_injected_input(injected)
                    graceful_shutdown_started_at = time.monotonic()

            if stdin_fd is not None and stdin_fd in ready:
                try:
                    parent_input = os.read(stdin_fd, 4096)
                except OSError:
                    parent_input = b""

                if not parent_input:
                    parent_stdin_closed = True
                else:
                    os.write(master_fd, parent_input)

        exit_code = process.wait()
        return PtyRunResult(exit_code=exit_code, transcript=b"".join(transcript_chunks).decode("utf-8", errors="replace"))
    finally:
        if previous_winch_handler is not None:
            signal.signal(signal.SIGWINCH, previous_winch_handler)
        if restore_tty is not None and stdin_fd is not None:
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, restore_tty)
        try:
            os.close(master_fd)
        except OSError:
            pass
        if slave_fd >= 0:
            try:
                os.close(slave_fd)
            except OSError:
                pass


def _noop_output(_chunk: bytes) -> str | None:
    return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m myteam.workflow.tty_wrapper <command> [args...]", file=sys.stderr)
        raise SystemExit(2)

    result = run_pty_session(sys.argv[1:], None, _noop_output)
    raise SystemExit(result.exit_code)
