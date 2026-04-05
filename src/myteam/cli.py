"""Command-line interface wiring for the myteam package."""
from __future__ import annotations

import fire

from .commands import (
    download_roster,
    get_role,
    get_skill,
    get_workflow,
    init,
    list_available_rosters,
    new_role,
    new_skill,
    new_workflow,
    remove,
    update_roster,
    version,
    workflow_resume,
    workflow_start,
    workflow_status,
)


def main(argv: list[str] | None = None):
    commands = {
        "init": init,
        "new": {
            "role": new_role,
            "skill": new_skill,
            "workflow": new_workflow,
        },
        "remove": remove,
        "get": {
            "role": get_role,
            "skill": get_skill,
            "workflow": get_workflow,
        },
        "download": download_roster,
        "update": update_roster,
        "list": list_available_rosters,
        "workflows": {
            "start": workflow_start,
            "resume": workflow_resume,
            "status": workflow_status,
        },
        "--version": version,
    }

    fire.Fire(commands)


if __name__ == "__main__":
    raise SystemExit(main())
