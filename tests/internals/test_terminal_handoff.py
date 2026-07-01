from __future__ import annotations

import sys

from myteam.workflows.execution.terminal import RealTerminal


class FakeTerminal(RealTerminal):
    def __init__(self) -> None:
        super().__init__()
        self.output = b""

    def write_stdout(self, data: bytes) -> None:
        self.output += data


def test_restore_visual_state_restores_terminal_modes_when_stdout_is_tty(monkeypatch) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    terminal = FakeTerminal()

    terminal.restore_visual_state()

    assert b"\x1b[?1049l" in terminal.output
    assert b"\x1b[?25h" in terminal.output


def test_restore_visual_state_is_quiet_when_stdout_is_not_tty(monkeypatch) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    terminal = FakeTerminal()

    terminal.restore_visual_state()

    assert terminal.output == b""
