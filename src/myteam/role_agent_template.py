#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def _print_block(text: str) -> None:
    sys.stdout.write(text)
    if text and not text.endswith("\n"):
        sys.stdout.write("\n")


def main() -> int:
    base = Path(__file__).resolve().parent  # .agents/<role>
    instructions = base / "instructions.md"
    if not instructions.exists():
        sys.stderr.write("instructions.md not found\n")
        return 1

    _print_block(instructions.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
