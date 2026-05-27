#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from myteam.utils import print_instructions, get_active_myteam_root, explain_skills, explain_roles, explain_tools, list_skills, \
    list_roles, list_tools, print_directory_tree


def main() -> int:
    base = Path(__file__).resolve().parent  # .myteam/<role>
    myteam = get_active_myteam_root(base)

    print_instructions(base)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
