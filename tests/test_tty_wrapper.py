from __future__ import annotations

import sys
from pathlib import Path

import pytest

from myteam.workflow.tty_wrapper import _InitialInputGate, run_pty_session


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


def test_run_pty_session_waits_for_ready_frame_before_sending_initial_input(
    capfd: pytest.CaptureFixture[str],
):
    result = run_pty_session(
        _helper_argv("gated_initial"),
        "hello from wrapper",
        lambda _chunk: None,
        initial_input_readiness_markers=[b"\x1b[?25h", b"\x1b[?2026l"],
        initial_input_quiet_period_seconds=0.05,
        inactivity_timeout_seconds=1,
        graceful_shutdown_timeout_seconds=1,
    )

    captured = capfd.readouterr()
    assert result.exit_code == 0
    assert "OpenAI Codex" in result.transcript
    assert "NO_EARLY_INPUT" in result.transcript
    assert "EARLY_INPUT:" not in result.transcript
    assert "LATE_INPUT:hello from wrapper" in result.transcript
    assert "LATE_INPUT:hello from wrapper" in captured.out


def test_initial_input_gate_waits_for_settled_output_before_pressing_enter():
    gate = _InitialInputGate(
        markers=[],
        quiet_period_seconds=0.06,
        pending_text="hello from wrapper",
    )

    assert gate.next_action(0.0) == "send_payload"
    assert gate.consume_payload() == "hello from wrapper"
    assert gate.next_action(0.01) is None

    gate.observe(b"composer redraw", observed_at=1.0)
    assert gate.next_action(1.04) is None
    assert gate.next_action(1.06) == "send_enter"

    gate.consume_enter()
    assert gate.next_action(1.07) is None


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
