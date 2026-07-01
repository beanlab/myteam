"""Policy-neutral live terminal output writers."""
from __future__ import annotations

import sys

from .pty_forwarding import BytesWriter, os_fd_writer
from .terminal import RealTerminal


def terminal_stdout_writer(terminal: RealTerminal, *, enabled: bool) -> BytesWriter | None:
    if not enabled:
        return None
    return terminal.write_stdout


def stderr_writer(*, enabled: bool) -> BytesWriter | None:
    if not enabled:
        return None
    try:
        return os_fd_writer(sys.stderr.fileno())
    except (OSError, ValueError, AttributeError):
        return None
