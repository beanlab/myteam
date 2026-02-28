#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from myteam.utils import print_instructions


def main() -> int:
    base = Path(__file__).resolve().parent  # .myteam/<role>
    print_instructions(base)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
