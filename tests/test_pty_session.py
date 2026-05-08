from __future__ import annotations

import sys
from pathlib import Path

import pytest

from myteam.workflow.agents.backends import get_backend
from myteam.workflow.terminal.pty_session import PtySession
from myteam.workflow.terminal.recording import TerminalRecording


HELPER = Path(__file__).resolve().parent / "helpers" / "tty_child.py"


def _helper_argv(mode: str, *args: str) -> list[str]:
    return [sys.executable, str(HELPER), mode, *args]


def test_pty_session_events_yield_output_and_support_enqueued_input(capfd: pytest.CaptureFixture[str]):
    backend = get_backend("codex")
    recording = TerminalRecording()

    with PtySession(_helper_argv("echo_initial"), inactivity_timeout_seconds=1) as session:
        events = session.events()
        while True:
            try:
                chunk = next(events)
            except StopIteration as exc:
                exit_code = exc.value
                break
            recording.feed(chunk)
            if "READY" in recording.snapshot() and "ECHO:" not in recording.snapshot():
                session.enqueue_input(backend.encode_input("hello from session"))

    captured = capfd.readouterr()
    assert exit_code == 0
    assert "ECHO:hello from session" in recording.snapshot()
    assert "ECHO:hello from session" in captured.out


def test_pty_session_preserves_backend_submit_sequence(capfd: pytest.CaptureFixture[str]):
    backend = get_backend("codex")
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
                session.enqueue_input(backend.encode_input("hello from session"))

    capfd.readouterr()
    assert exit_code == 0
    assert "RIGHT_ARROW_SUBMIT" in recording.snapshot()
    assert "MISSING_RIGHT_ARROW" not in recording.snapshot()


def test_pty_session_times_out_after_inactivity():
    with PtySession(_helper_argv("silent"), inactivity_timeout_seconds=1) as session:
        with pytest.raises(TimeoutError, match="became inactive for 1 seconds"):
            events = session.events()
            next(events)
