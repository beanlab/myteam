"""Live terminal output tracking for workflow supervision."""
from __future__ import annotations

import sys

from .pty_forwarding import BytesWriter, os_fd_writer
from .terminal import RealTerminal, has_screen_rewriting_control, strip_ansi_csi


class LiveOutputTracker:
    """Tracks forwarded live output so final result text is visually separated."""

    def __init__(self):
        self.forwarded_live_output = False
        self.forwarded_screen_rewriting_output = False
        self.live_output_ended_with_newline = True

    def stdout_writer(self, terminal: RealTerminal, *, enabled: bool) -> BytesWriter | None:
        if not enabled:
            return None

        def _write(data: bytes):
            self.notice(data)
            terminal.write_stdout(data)

        return _write

    def stderr_writer(self, *, enabled: bool) -> BytesWriter | None:
        writer = _stderr_writer() if enabled else None
        if writer is None:
            return None

        def _write(data: bytes):
            self.notice(data)
            writer(data)

        return _write

    def notice(self, data: bytes):
        if has_screen_rewriting_control(data):
            self.forwarded_screen_rewriting_output = True
        display_text = strip_ansi_csi(data)
        if not display_text:
            return
        self.forwarded_live_output = True
        self.live_output_ended_with_newline = display_text.endswith(b"\n")

    def finish(self, terminal: RealTerminal, *, enabled: bool):
        if not enabled:
            return
        terminal.restore_visual_state()
        if self.forwarded_screen_rewriting_output:
            terminal.clear()
            self.live_output_ended_with_newline = True
            return
        if self.forwarded_live_output and not self.live_output_ended_with_newline:
            terminal.write_stdout(b"\r\n")
            self.live_output_ended_with_newline = True


def _stderr_writer() -> BytesWriter | None:
    try:
        return os_fd_writer(sys.stderr.fileno())
    except (OSError, ValueError, AttributeError):
        return None
