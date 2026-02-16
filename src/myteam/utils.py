import sys
from pathlib import Path


def _print_block(text: str) -> None:
    sys.stdout.write(text)
    if text and not text.endswith("\n"):
        sys.stdout.write("\n")


def print_instructions(base: Path):
    instructions = base / "instructions.md"
    if instructions.exists():
        _print_block(instructions.read_text(encoding="utf-8"))


def print_team_info(agents_root: Path, base: Path):
    for role_dir in sorted(p for p in agents_root.iterdir() if p.is_dir()):
        if role_dir == base:
            continue
        info = role_dir / "info.md"
        if not info.exists():
            continue
        _print_block(f"\n## {role_dir.name}\n")
        _print_block(info.read_text(encoding="utf-8"))