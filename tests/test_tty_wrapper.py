from __future__ import annotations

import sys
from pathlib import Path

import pytest

from myteam.workflow.tty_wrapper import run_pty_session


HELPER = Path(__file__).resolve().parent / "helpers" / "tty_child.py"


def _helper_argv(mode: str, *args: str) -> list[str]:
    return [sys.executable, str(HELPER), mode, *args]


def test_run_pty_session_sends_initial_input_with_enter(capfd: pytest.CaptureFixture[str]):
    result = run_pty_session(
        _helper_argv("echo_initial"),
        "hello from wrapper",
        lambda _chunk: None,
        inactivity_timeout_seconds=1,
        graceful_shutdown_timeout_seconds=1,
    )

    captured = capfd.readouterr()
    assert result.exit_code == 0
    assert "READY" in result.transcript
    assert "ECHO:hello from wrapper" in result.transcript
    assert "ECHO:hello from wrapper" in captured.out


def test_run_pty_session_callback_can_inject_quit_command(capfd: pytest.CaptureFixture[str]):
    def on_output(chunk: bytes) -> str | None:
        return "/quit\n" if b"dog" in chunk else None

    result = run_pty_session(
        _helper_argv("wait_for_quit"),
        None,
        on_output,
        inactivity_timeout_seconds=1,
        graceful_shutdown_timeout_seconds=1,
    )

    captured = capfd.readouterr()
    assert result.exit_code == 0
    assert "dog" in result.transcript
    assert "INPUT:/quit" in result.transcript
    assert "QUIT_ACK" in result.transcript
    assert "QUIT_ACK" in captured.out


def test_run_pty_session_keeps_trailing_output_after_injected_quit(capfd: pytest.CaptureFixture[str]):
    def on_output(chunk: bytes) -> str | None:
        return "/quit\n" if b"dog" in chunk else None

    result = run_pty_session(
        _helper_argv("trailing_after_quit"),
        None,
        on_output,
        inactivity_timeout_seconds=1,
        graceful_shutdown_timeout_seconds=1,
    )

    capfd.readouterr()
    assert result.exit_code == 0
    assert "QUIT_ACK" in result.transcript
    assert "TRAILING_OUTPUT" in result.transcript


def test_run_pty_session_preserves_child_exit_code(capfd: pytest.CaptureFixture[str]):
    result = run_pty_session(
        _helper_argv("exit_code", "7"),
        None,
        lambda _chunk: None,
        inactivity_timeout_seconds=1,
        graceful_shutdown_timeout_seconds=1,
    )

    capfd.readouterr()
    assert result.exit_code == 7
    assert "EXITING" in result.transcript


def test_run_pty_session_times_out_after_inactivity(capfd: pytest.CaptureFixture[str]):
    with pytest.raises(TimeoutError, match="became inactive for 1 seconds"):
        run_pty_session(
            _helper_argv("silent"),
            None,
            lambda _chunk: None,
            inactivity_timeout_seconds=1,
            graceful_shutdown_timeout_seconds=1,
        )

    capfd.readouterr()
