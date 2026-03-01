#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from myteam.utils import get_myteam_root, print_instructions, list_dir, explain_roles


def main() -> int:
    base = Path(__file__).resolve().parent  # e.g. .myteam/main
    myteam_root = get_myteam_root(base)

    print_instructions(base)
    explain_roles()
    list_dir(myteam_root, myteam_root, [base.name])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
