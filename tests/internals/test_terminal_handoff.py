from __future__ import annotations

import sys

from myteam.workflows.execution.terminal import RealTerminal


class FakeTerminal(RealTerminal):
    def __init__(self) -> None:
        super().__init__()
        self.output = b""

    def write_stdout(self, data: bytes) -> None:
        self.output += data

    def winsize(self) -> tuple[int, int]:
        return (3, 80)


def test_separate_interactive_region_scrolls_screen_rewriting_output(monkeypatch) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    terminal = FakeTerminal()

    terminal.separate_interactive_region(
        had_output=True,
        ended_with_newline=False,
        had_screen_rewriting_output=True,
    )

    assert terminal.output.endswith(b"\r\n\r\n\r\n")


def test_separate_interactive_region_adds_small_gap_for_plain_output(monkeypatch) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    terminal = FakeTerminal()

    terminal.separate_interactive_region(
        had_output=True,
        ended_with_newline=True,
        had_screen_rewriting_output=False,
    )

    assert terminal.output.endswith(b"\r\n\r\n")


def test_separate_interactive_region_is_quiet_without_visible_output(monkeypatch) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    terminal = FakeTerminal()

    terminal.separate_interactive_region(
        had_output=False,
        ended_with_newline=True,
        had_screen_rewriting_output=False,
    )

    assert terminal.output
    assert b"\r\n" not in terminal.output
