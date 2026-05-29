#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from myteam.utils import get_skills, list_roles, print_instructions


def main() -> int:
    base = Path(__file__).resolve().parent
    display_root = base.parent

    print_instructions(base)
    get_skills(base, display_root, [])
    list_roles(base, display_root, [])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
