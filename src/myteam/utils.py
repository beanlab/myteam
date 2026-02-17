from pathlib import Path


def _print_block(text: str) -> None:
    print(text.rstrip('\n'))


def print_instructions(base: Path):
    instructions = base / "instructions.md"
    if instructions.exists():
        _print_block(instructions.read_text(encoding="utf-8"))


def print_team_info(agents_root: Path, base: Path):
    print()
    print(' Team Members '.center(30, '*'))
    for role_dir in sorted(p for p in agents_root.iterdir() if p.is_dir()):
        if role_dir == base:
            continue
        info = role_dir / "info.md"
        if not info.exists():
            continue
        print(f" {role_dir.name} ".center(30, '-'))
        print(info.read_text(encoding="utf-8").rstrip('\n'))
