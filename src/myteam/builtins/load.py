#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from myteam.utils import builtin_skill_dir, list_roles, list_skills, list_tools, print_instructions


def main() -> int:
    base = Path(__file__).resolve().parent
    display_root = base.parent

    print_instructions(base)
    list_roles(base, display_root, [])
    list_skills(base, display_root, [])
    list_tools(base, display_root, [])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
