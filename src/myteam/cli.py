"""Command-line interface wiring for the myteam package."""
from __future__ import annotations

import fire

from .commands import (
    download_roster,
    get_role,
    get_skill,
    init,
    list_available_rosters,
    new_role,
    new_skill,
    remove,
    start,
    update_roster,
    version,
)


def main(argv: list[str] | None = None):
    commands = {
        "init": init,
        "new": {
            "role": new_role,
            "skill": new_skill
        },
        "remove": remove,
        "start": start,
        "get": {
            "role": get_role,
            "skill": get_skill,
        },
        "download": download_roster,
        "update": update_roster,
        "list": list_available_rosters,
        "--version": version,
    }

    fire.Fire(commands)


if __name__ == "__main__":
    raise SystemExit(main())
