#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from myteam.upgrade import print_upgrade_notice
from myteam.frontmatter import print_instructions, get_active_myteam_root, explain_skills, explain_tasks, explain_roles, get_skills, \
    list_roles, list_tasks, print_directory_tree


def main() -> int:
    base = Path(__file__).resolve().parent  # .myteam/<role>
    myteam = get_active_myteam_root(base)

    print_instructions(base)
    print_upgrade_notice(myteam)
    print_directory_tree(myteam.parent)

    explain_skills()
    get_skills(base, myteam, [])

    explain_tasks()
    list_tasks(myteam, myteam, [])

    explain_roles()
    list_roles(base, myteam, [])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
