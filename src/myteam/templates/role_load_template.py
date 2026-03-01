#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from myteam.utils import print_instructions, get_myteam_root, list_dir, explain_skills, explain_roles


def main() -> int:
    base = Path(__file__).resolve().parent  # .myteam/<role>
    print_instructions(base)
    # TODO - only show these if roles or skills exist
    explain_skills()
    explain_roles()
    list_dir(base, get_myteam_root(base), [])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
