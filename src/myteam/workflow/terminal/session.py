from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import threading
from typing import Any

from .control_channel import ChildWorkflowRequest, ControlChannel
from .pty_session import PtySession
from .recording import TerminalRecording
from .result_channel import ResultChannel


@dataclass
class TerminalSessionResult:
    exit_code: int
    transcript: str
    payload: Any | None
    control_request: ChildWorkflowRequest | None = None


def run_terminal_session(
    argv: list[str],
    *,
    exit_input: bytes,
    payload_validator: Callable[[Any], str | None] | None = None,
    cwd: Path | str | None = None,
    timeout: int = 300,
    session_nonce: str | None = None,
) -> TerminalSessionResult:
    recording = TerminalRecording()
    with ResultChannel(session_nonce=session_nonce, payload_validator=payload_validator) as result_channel, ControlChannel(session_nonce=session_nonce) as control_channel:
        with PtySession(
            argv,
            env=None,
            cwd=cwd,
            timeout=timeout,
        ) as session:
            _start_result_watcher(
                session,
                result_channel,
                exit_input=exit_input,
            )
            _start_control_watcher(
                session,
                control_channel,
                exit_input=exit_input,
            )

            events = session.events()
            while True:
                try:
                    chunk = next(events)
                except StopIteration as exc:
                    exit_code = exc.value
                    break

                recording.feed(chunk)

            payload = result_channel.wait(timeout=0.1)
            control_request = control_channel.wait(timeout=0.1)
            return TerminalSessionResult(
                exit_code=exit_code,
                transcript=recording.snapshot(),
                payload=payload,
                control_request=control_request,
            )


def _start_result_watcher(
    session: PtySession,
    result_channel: ResultChannel,
    *,
    exit_input: bytes,
) -> None:
    def watch() -> None:
        while not result_channel.closed.is_set():
            payload = result_channel.wait(timeout=0.1)
            if payload is None:
                continue
            session.enqueue_input(exit_input)
            return

    threading.Thread(target=watch, daemon=True).start()


def _start_control_watcher(
    session: PtySession,
    control_channel: ControlChannel,
    *,
    exit_input: bytes,
) -> None:
    def watch() -> None:
        while not control_channel.closed.is_set():
            request = control_channel.wait(timeout=0.1)
            if request is None:
                continue
            session.enqueue_input(exit_input)
            return

    threading.Thread(target=watch, daemon=True).start()
