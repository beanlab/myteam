from __future__ import annotations

from collections.abc import Callable

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
    raise NotImplementedError("Workflow PTY execution is not implemented yet")
