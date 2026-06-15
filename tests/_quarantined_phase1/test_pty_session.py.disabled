from __future__ import annotations

import sys
from pathlib import Path

import pytest

from myteam.tasks.agents.agent_utils import encode_input
from myteam.tasks.terminal.pty_session import PtySession
from myteam.tasks.terminal.recording import TerminalRecording


HELPER = Path(__file__).resolve().parent / "helpers" / "tty_child.py"


def _helper_argv(mode: str, *args: str) -> list[str]:
    return [sys.executable, str(HELPER), mode, *args]


def test_pty_session_events_yield_output_and_support_enqueued_input(capfd: pytest.CaptureFixture[str]):
    recording = TerminalRecording()

    with PtySession(_helper_argv("wait_for_quit"), timeout=1) as session:
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

    with PtySession(_helper_argv("require_submit_sequence"), timeout=1) as session:
        events = session.events()
        while True:
            try:
                chunk = next(events)
            except StopIteration as exc:
                exit_code = exc.value
                break
            recording.feed(chunk)
            if "READY" in recording.snapshot() and "RIGHT_ARROW_SUBMIT" not in recording.snapshot():
                session.enqueue_input(encode_input("/quit"))

    capfd.readouterr()
    assert exit_code == 0
    assert "RAW_ECHO:/quit" in recording.snapshot()
    assert "RIGHT_ARROW_SUBMIT" in recording.snapshot()
    assert "MISSING_RIGHT_ARROW" not in recording.snapshot()


def test_pty_session_gives_child_a_controlling_terminal(capfd: pytest.CaptureFixture[str]):
    recording = TerminalRecording()

    with PtySession(_helper_argv("controlling_tty"), timeout=1) as session:
        events = session.events()
        while True:
            try:
                chunk = next(events)
            except StopIteration as exc:
                exit_code = exc.value
                break
            recording.feed(chunk)

    capfd.readouterr()
    assert exit_code == 0
    assert "STDIN_ISATTY:True" in recording.snapshot()
    assert "DEV_TTY_OK" in recording.snapshot()


def test_pty_session_times_out_after_inactivity():
    with PtySession(_helper_argv("silent"), timeout=1) as session:
        with pytest.raises(TimeoutError, match="became inactive for 1 seconds"):
            events = session.events()
            next(events)
