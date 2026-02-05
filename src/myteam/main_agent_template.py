#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def _print_block(text: str) -> None:
    sys.stdout.write(text)
    if text and not text.endswith("\n"):
        sys.stdout.write("\n")


def main() -> int:
    base = Path(__file__).resolve().parent  # .agents/main
    agents_root = base.parent

    instructions = base / "instructions.md"
    if instructions.exists():
        _print_block(instructions.read_text(encoding="utf-8"))

    for role_dir in sorted(p for p in agents_root.iterdir() if p.is_dir()):
        if role_dir == base:
            continue
        info = role_dir / "info.md"
        if not info.exists():
            continue
        _print_block(f"\n## info for {role_dir.name}\n")
        _print_block(info.read_text(encoding="utf-8"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
