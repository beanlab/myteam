from __future__ import annotations

from pathlib import Path
import os
import pty
import sys
import threading
import textwrap

import pytest

from myteam.workflow import tty_wrapper
from myteam.workflow.tty_wrapper import run_pty_session


def _write_agent_script(tmp_path: Path) -> Path:
    script = tmp_path / "test_agent.py"
    script.write_text(
        textwrap.dedent(
            """
            import sys

            print("READY", flush=True)

            for line in sys.stdin:
                text = line.rstrip("\\n")
                print(f"INPUT:{text}", flush=True)
                if text == "hello":
                    print("OBJECTIVE_COMPLETE", flush=True)
                if text == "/quit":
                    print("EXITING", flush=True)
                    print("TRAILING", flush=True)
                    break
            """
        ),
        encoding="utf-8",
    )
    return script


def test_run_pty_session_captures_output_and_writes_callback_responses(tmp_path: Path):
    script = _write_agent_script(tmp_path)
    seen_chunks: list[bytes] = []

    def on_output(chunk: bytes) -> str | None:
        seen_chunks.append(chunk)
        if b"OBJECTIVE_COMPLETE" in b"".join(seen_chunks):
            return "/quit\n"
        return None

    result = run_pty_session(
        [sys.executable, str(script)],
        "hello\n",
        on_output,
        inactivity_timeout_seconds=5,
        graceful_shutdown_timeout_seconds=5,
    )

    assert result.exit_code == 0
    assert "READY" in result.transcript
    assert "INPUT:hello" in result.transcript
    assert "OBJECTIVE_COMPLETE" in result.transcript
    assert "INPUT:/quit" in result.transcript
    assert "EXITING" in result.transcript
    assert "TRAILING" in result.transcript


def test_run_pty_session_raises_on_inactivity_timeout(tmp_path: Path):
    script = tmp_path / "silent_agent.py"
    script.write_text(
        textwrap.dedent(
            """
            import time

            time.sleep(2)
            """
        ),
        encoding="utf-8",
    )

    with pytest.raises(TimeoutError, match="inactivity timeout"):
        run_pty_session(
            [sys.executable, str(script)],
            None,
            lambda chunk: None,
            inactivity_timeout_seconds=1,
            graceful_shutdown_timeout_seconds=1,
        )


def test_run_pty_session_interactive_passthrough_forwards_parent_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    script = _write_agent_script(tmp_path)
    parent_stdin_master, parent_stdin_slave = pty.openpty()
    echoed_chunks: list[bytes] = []

    monkeypatch.setattr(tty_wrapper, "_has_interactive_parent_terminal", lambda: True)
    monkeypatch.setattr(
        tty_wrapper, "_parent_terminal_fds", lambda: (parent_stdin_slave, sys.__stdout__.fileno())
    )
    monkeypatch.setattr(
        tty_wrapper, "_echo_to_parent_stdout", lambda chunk: echoed_chunks.append(chunk)
    )

    def _feed_parent_input() -> None:
        os.write(parent_stdin_master, b"typed-through-parent\n")
        os.write(parent_stdin_master, b"/quit\n")

    feeder = threading.Timer(0.3, _feed_parent_input)
    feeder.start()
    try:
        result = run_pty_session(
            [sys.executable, str(script)],
            None,
            lambda chunk: None,
            inactivity_timeout_seconds=5,
            graceful_shutdown_timeout_seconds=5,
        )
    finally:
        feeder.cancel()
        os.close(parent_stdin_master)
        os.close(parent_stdin_slave)

    echoed_output = b"".join(echoed_chunks).decode("utf-8", errors="replace")
    assert result.exit_code == 0
    assert "READY" in result.transcript
    assert "INPUT:typed-through-parent" in result.transcript
    assert "INPUT:/quit" in result.transcript
    assert "EXITING" in result.transcript
    assert "READY" in echoed_output
    assert "INPUT:typed-through-parent" in echoed_output


def test_run_pty_session_types_callback_input_one_byte_at_a_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    script = _write_agent_script(tmp_path)
    writes: list[bytes] = []
    tracked_master_fd = -1
    original_write = tty_wrapper.os.write
    original_openpty = tty_wrapper.pty.openpty

    def tracking_openpty() -> tuple[int, int]:
        nonlocal tracked_master_fd
        tracked_master_fd, slave_fd = original_openpty()
        return tracked_master_fd, slave_fd

    def tracking_write(fd: int, data: bytes) -> int:
        if fd == tracked_master_fd:
            writes.append(data)
        return original_write(fd, data)

    seen_chunks: list[bytes] = []
    injected = False

    def on_output(chunk: bytes) -> str | None:
        nonlocal injected
        seen_chunks.append(chunk)
        if not injected and b"OBJECTIVE_COMPLETE" in b"".join(seen_chunks):
            injected = True
            return "/quit\r"
        return None

    monkeypatch.setattr(tty_wrapper.pty, "openpty", tracking_openpty)
    monkeypatch.setattr(tty_wrapper.os, "write", tracking_write)

    result = run_pty_session(
        [sys.executable, str(script)],
        "hello\n",
        on_output,
        inactivity_timeout_seconds=5,
        graceful_shutdown_timeout_seconds=5,
    )

    callback_keystrokes = writes[-6:]

    assert result.exit_code == 0
    assert "EXITING" in result.transcript
    assert callback_keystrokes == [b"/", b"q", b"u", b"i", b"t", b"\r"]


def test_run_pty_session_bulk_writes_initial_input_but_types_callback_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    script = _write_agent_script(tmp_path)
    writes: list[bytes] = []
    tracked_master_fd = -1
    original_write = tty_wrapper.os.write
    original_openpty = tty_wrapper.pty.openpty

    def tracking_openpty() -> tuple[int, int]:
        nonlocal tracked_master_fd
        tracked_master_fd, slave_fd = original_openpty()
        return tracked_master_fd, slave_fd

    def tracking_write(fd: int, data: bytes) -> int:
        if fd == tracked_master_fd:
            writes.append(data)
        return original_write(fd, data)

    seen_chunks: list[bytes] = []
    injected = False
    initial_input = "hello\n"

    def on_output(chunk: bytes) -> str | None:
        nonlocal injected
        seen_chunks.append(chunk)
        if not injected and b"OBJECTIVE_COMPLETE" in b"".join(seen_chunks):
            injected = True
            return "/quit\r"
        return None

    monkeypatch.setattr(tty_wrapper.pty, "openpty", tracking_openpty)
    monkeypatch.setattr(tty_wrapper.os, "write", tracking_write)

    result = run_pty_session(
        [sys.executable, str(script)],
        initial_input,
        on_output,
        inactivity_timeout_seconds=5,
        graceful_shutdown_timeout_seconds=5,
    )

    assert result.exit_code == 0
    assert initial_input.encode("utf-8") in writes
    assert writes[-6:] == [b"/", b"q", b"u", b"i", b"t", b"\r"]
