"""Command-line interface wiring for the myteam package."""
from __future__ import annotations

import functools

import fire

from .skills import explain_skills, print_load_skill
from .prefix import _set_global_prefix_env_var
from .commands import (
    changelog,
    download_roster,
    load_skill,
    get_skills,
    get_workflows,
    init,
    list_available_rosters,
    new_skill,
    new_workflow,
    remove,
    start_workflow,
    update_roster,
    version,
)


def delegate_commands(command_map):
    def decorate(cls):
        for name, fn in command_map.items():
            def make_wrapper(f):
                @functools.wraps(f)
                def wrapper(self, *args, **kwargs):
                    return f(*args, **kwargs)

                return wrapper

            setattr(cls, name, make_wrapper(fn))

        return cls

    return decorate


def main():
    commands = {
        "init": init,
        "new": {
            "skill": new_skill,
            "workflow": new_workflow,
        },
        "explain": {
            "skills": lambda: print(explain_skills()),
            "workflows": lambda: print(explain_workflows()),
        },
        "get": {
            "skills": lambda: print(get_skills()),
            "workflows": get_workflows,
        },
        "start": start_workflow,
        "load": print_load_skill,

        "remove": remove,  # TODO - keep?

        "download": download_roster,  # TODO - bundle these?
        "update": update_roster,
        "list": list_available_rosters,
        "changelog": changelog,
        "--version": version,
    }

    @delegate_commands(commands)
    class MyTeam:
        def __init__(self, prefix: str = ".myteam"):
            _set_global_prefix_env_var(prefix)

    fire.Fire(MyTeam)
    

if __name__ == "__main__":
    main()
