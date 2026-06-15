"""Real terminal handling for the workflow supervisor."""
from __future__ import annotations

from collections.abc import Callable
import os
import shutil
import signal
import sys
import termios
import tty
from typing import Any


Winsize = tuple[int, int]


class RealTerminal:
    """Owns raw-mode setup, output, input, clearing, and resize callbacks."""

    def __init__(self, *, on_resize: Callable[[Winsize], None] | None = None) -> None:
        self.on_resize = on_resize
        self.stdin_fd: int | None = None
        try:
            self.stdout_fd: int = sys.stdout.fileno()
        except (OSError, ValueError, AttributeError):
            self.stdout_fd = 1
        self._restore_tty: list[Any] | None = None
        self._previous_winch_handler: Any = None

    def __enter__(self) -> "RealTerminal":
        if sys.stdin.isatty():
            try:
                self.stdin_fd = sys.stdin.fileno()
            except (OSError, ValueError, AttributeError):
                self.stdin_fd = None
                self._previous_winch_handler = signal.getsignal(signal.SIGWINCH)
                signal.signal(signal.SIGWINCH, self._handle_winch)
                return self
            self._restore_tty = termios.tcgetattr(self.stdin_fd)
            tty.setraw(self.stdin_fd)
        self._previous_winch_handler = signal.getsignal(signal.SIGWINCH)
        signal.signal(signal.SIGWINCH, self._handle_winch)
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        self.restore()

    @property
    def can_read_stdin(self) -> bool:
        return self.stdin_fd is not None

    def read_stdin(self, size: int = 4096) -> bytes:
        if self.stdin_fd is None:
            return b""
        return os.read(self.stdin_fd, size)

    def write_stdout(self, data: bytes) -> None:
        if data:
            os.write(self.stdout_fd, data)

    def clear(self) -> None:
        if sys.stdout.isatty():
            self.write_stdout(b"\x1b[2J\x1b[H")

    def winsize(self) -> Winsize:
        size = shutil.get_terminal_size(fallback=(80, 24))
        winsize = (size.lines, size.columns)
        stdin_fd = self.stdin_fd
        if stdin_fd is None and sys.stdin.isatty():
            try:
                stdin_fd = sys.stdin.fileno()
            except (OSError, ValueError, AttributeError):
                stdin_fd = None
        if stdin_fd is not None:
            try:
                winsize = termios.tcgetwinsize(stdin_fd)
            except OSError:
                pass
        return winsize

    def restore(self) -> None:
        if self._previous_winch_handler is not None:
            signal.signal(signal.SIGWINCH, self._previous_winch_handler)
            self._previous_winch_handler = None
        if self._restore_tty is not None and self.stdin_fd is not None:
            termios.tcsetattr(self.stdin_fd, termios.TCSADRAIN, self._restore_tty)
            self._restore_tty = None

    def _handle_winch(self, _signum: int, _frame: Any) -> None:
        if self.on_resize is not None:
            self.on_resize(self.winsize())
