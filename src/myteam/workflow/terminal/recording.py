from __future__ import annotations


class TerminalRecording:
    def __init__(self, *, columns: int = 80, lines: int = 24) -> None:
        self.columns = columns
        self.lines = lines
        self._parts: list[str] = []

    def feed(self, chunk: bytes) -> str:
        self._parts.append(chunk.decode("utf-8", errors="replace"))
        return self.snapshot()

    def snapshot(self) -> str:
        return "".join(self._parts)
