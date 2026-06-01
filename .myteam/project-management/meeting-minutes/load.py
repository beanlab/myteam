#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from myteam.frontmatter import get_active_myteam_root, get_skills, list_roles, list_tools, print_instructions, \
    print_directory_tree


def main() -> int:
    base = Path(__file__).resolve().parent  # .myteam/<role>
    print_instructions(base)
    myteam = get_active_myteam_root(base)
    get_skills(base, myteam, [])
    list_tools(base, myteam.parent, [])
    list_roles(base, myteam, [])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
