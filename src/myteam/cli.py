"""Command-line interface wiring for the myteam package."""
from __future__ import annotations

import functools

import fire

from .commands import changelog, onboard, version
from .explain import explain_resources
from .listing import list_resources
from .skills import new_skill, load_skill
from .workflows import new_workflow, start_workflow_cli, report_result


def printed(func):
    @functools.wraps(func)
    def new_func(*args, **kwargs):
        result = func(*args, **kwargs)
        if result is not None:
            print(result, end="")
    return new_func


def main():
    commands = {
        "explain": printed(explain_resources),
        "list": printed(list_resources),
        "new": {
            "skill": new_skill,
            "workflow": new_workflow
        },
        "load": printed(load_skill),
        "onboard": printed(onboard),
        "start": start_workflow_cli,
        "result": report_result,
        "version": version,
        "changelog": changelog,
    }

    fire.Fire(commands)


if __name__ == "__main__":
    main()
