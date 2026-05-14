from __future__ import annotations

import sys
from pathlib import Path

import pytest

from myteam.workflow.agents.codex import EXIT_SEQUENCE
from myteam.workflow.terminal.pty_session import PtySession
from myteam.workflow.terminal.recording import TerminalRecording


HELPER = Path(__file__).resolve().parent / "helpers" / "tty_child.py"


def _helper_argv(mode: str, *args: str) -> list[str]:
    return [sys.executable, str(HELPER), mode, *args]


def test_pty_session_events_yield_output_and_support_enqueued_input(capfd: pytest.CaptureFixture[str]):
    recording = TerminalRecording()

    with PtySession(_helper_argv("wait_for_quit"), inactivity_timeout_seconds=1) as session:
        events = session.events()
        while True:
            try:
                chunk = next(events)
            except StopIteration as exc:
                exit_code = exc.value
                break
            recording.feed(chunk)
            if "dog" in recording.snapshot() and "QUIT_ACK" not in recording.snapshot():
                session.enqueue_input(b"/quit\n")

    captured = capfd.readouterr()
    assert exit_code == 0
    assert "QUIT_ACK" in recording.snapshot()
    assert "QUIT_ACK" in captured.out


def test_pty_session_exit_input_preserves_backend_submit_sequence(capfd: pytest.CaptureFixture[str]):
    recording = TerminalRecording()

    with PtySession(_helper_argv("require_submit_sequence"), inactivity_timeout_seconds=1) as session:
        events = session.events()
        while True:
            try:
                chunk = next(events)
            except StopIteration as exc:
                exit_code = exc.value
                break
            recording.feed(chunk)
            if "READY" in recording.snapshot() and "RIGHT_ARROW_SUBMIT" not in recording.snapshot():
                session.enqueue_input(EXIT_SEQUENCE)

    capfd.readouterr()
    assert exit_code == 0
    assert "RAW_ECHO:/quit" in recording.snapshot()
    assert "RIGHT_ARROW_SUBMIT" in recording.snapshot()
    assert "MISSING_RIGHT_ARROW" not in recording.snapshot()


def test_pty_session_times_out_after_inactivity():
    with PtySession(_helper_argv("silent"), inactivity_timeout_seconds=1) as session:
        with pytest.raises(TimeoutError, match="became inactive for 1 seconds"):
            events = session.events()
            next(events)
