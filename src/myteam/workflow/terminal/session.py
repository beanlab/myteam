from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import threading
import time

from .pty_session import PtySession
from .recording import TerminalRecording
from .result_channel import ResultChannel


@dataclass
class TerminalSessionResult:
    exit_code: int
    transcript: str
    payload: Any | None


def run_terminal_session(
    argv: list[str],
    *,
    initial_input: bytes,
    exit_input: bytes,
    inactivity_timeout_seconds: int = 300,
    graceful_shutdown_timeout_seconds: int = 30,
) -> TerminalSessionResult:
    recording = TerminalRecording()
    with ResultChannel() as result_channel:
        with PtySession(
            argv,
            env=result_channel.env,
            inactivity_timeout_seconds=inactivity_timeout_seconds,
        ) as session:
            _start_result_watcher(
                session,
                result_channel,
                exit_input=exit_input,
                graceful_shutdown_timeout_seconds=graceful_shutdown_timeout_seconds,
            )

            sent_initial_input = False
            events = session.events()
            while True:
                try:
                    chunk = next(events)
                except StopIteration as exc:
                    exit_code = exc.value
                    break

                recording.feed(chunk)
                if not sent_initial_input:
                    session.enqueue_input(initial_input)
                    sent_initial_input = True

            payload = result_channel.wait(timeout=0.1)
            return TerminalSessionResult(
                exit_code=exit_code,
                transcript=recording.snapshot(),
                payload=payload,
            )


def _start_result_watcher(
    session: PtySession,
    result_channel: ResultChannel,
    *,
    exit_input: bytes,
    graceful_shutdown_timeout_seconds: int,
) -> None:
    def watch() -> None:
        while not result_channel.closed.is_set():
            payload = result_channel.wait(timeout=0.1)
            if payload is None:
                continue
            session.enqueue_input(exit_input)
            if graceful_shutdown_timeout_seconds > 0:
                time.sleep(graceful_shutdown_timeout_seconds)
                process = session.process
                if process is not None and process.poll() is None:
                    process.terminate()
                    time.sleep(0.2)
                    if process.poll() is None:
                        process.kill()
            return

    threading.Thread(target=watch, daemon=True).start()
