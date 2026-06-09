"""Command-line interface wiring for the myteam package."""
from __future__ import annotations

import functools

import fire

from .commands import changelog, version
from .rosters import download_roster, list_available_rosters, update_roster
from .explain import explain_resources
from .listing import list_resources
# from .skills import explain_skills
from .skills import new_skill, load_skill
# from .workflows.commands import new_workflow, start_workflow


def printed(func):
    def new_func(*args, **kwargs):
        print(func(*args, **kwargs))
    return new_func


def main():
    commands = {
        "explain": printed(explain_resources),
        "list": printed(list_resources),
        "load": printed(load_skill),
        # "start": printed(start_workflow),
        "new": {
            "skill": new_skill,
            # "workflow": new_workflow
        },
        "version": version,
        "changelog": changelog,
        "rosters": {
            "list": printed(list_available_rosters),
            "download": download_roster,
            "update": update_roster,
        }
    }

    fire.Fire(commands)


if __name__ == "__main__":
    main()
