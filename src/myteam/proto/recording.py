"""Tiny transcript recorder for prototype PTY sessions."""
from __future__ import annotations


class TerminalRecording:
    def __init__(self) -> None:
        self._parts: list[str] = []

    def feed(self, chunk: bytes) -> None:
        self._parts.append(chunk.decode("utf-8", errors="replace"))

    def snapshot(self) -> str:
        return "".join(self._parts)
