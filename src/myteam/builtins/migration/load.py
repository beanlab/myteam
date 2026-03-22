#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from myteam.upgrade import print_pending_migrations
from myteam.utils import (
    builtin_skill_dir,
    get_active_myteam_root,
    list_roles,
    list_skills,
    list_tools,
    print_directory_tree,
    print_instructions,
)


def main() -> int:
    base = Path(__file__).resolve().parent
    builtin_root = builtin_skill_dir("builtins")
    myteam = get_active_myteam_root(base)

    print_instructions(base)
    print_pending_migrations(myteam)
    print_directory_tree(myteam)
    list_roles(base, builtin_root, [])
    list_skills(base, builtin_root, [])
    list_tools(base, builtin_root, [])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
