#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from myteam.upgrade import print_pending_migrations
from myteam.utils import print_instructions, get_active_myteam_root, list_roles, list_skills, list_tools


def main() -> int:
    base = Path(__file__).resolve().parent
    myteam = get_active_myteam_root(base)

    print_instructions(base)
    print_pending_migrations(myteam)
    list_skills(base, myteam, [])
    list_tools(base, myteam, [])
    list_roles(base, myteam, [])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
