"""Command-line interface wiring for the myteam package."""
from __future__ import annotations

import argparse
import sys

import fire

from .commands import (
    changelog,
    download_roster,
    get_role,
    get_skill,
    get_skills,
    get_tasks,
    get_task,
    init,
    list_available_rosters,
    new_role,
    new_skill,
    new_task,
    new_workflow,
    remove,
    start,
    update_roster,
    version,
)
from .tasks.execution.cli_commands import (
    task_result as task_result_command,
    task_start as task_start_command,
)


def _run_task_cli(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="myteam task")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("task")
    start_parser.add_argument("--session-nonce", required=True)
    start_parser.add_argument("--json")
    start_parser.add_argument("--text")

    result_parser = subparsers.add_parser("result")
    result_parser.add_argument("--session-nonce", required=True)
    result_parser.add_argument("--json")
    result_parser.add_argument("--text")

    args = parser.parse_args(argv)
    if args.command == "start":
        task_start_command(
            args.task,
            json=args.json,
            text=args.text,
            session_nonce=args.session_nonce,
        )
        return
    task_result_command(
        json=args.json,
        text=args.text,
        session_nonce=args.session_nonce,
    )


def main(argv: list[str] | None = None):
    args = sys.argv[1:] if argv is None else list(argv)
    if args[:1] == ["task"]:
        _run_task_cli(args[1:])
        return 0

    commands = {
        "init": init,
        "new": {
            "role": new_role,
            "skill": new_skill,
            "task": new_task,
            "workflow": new_workflow,
        },
        "remove": remove,
        "get": {
            "role": get_role,
            "skill": get_skill,
            "task": get_task,
            "skills": get_skills,
            "tasks": get_tasks,
        },
        "get_skills": get_skills,
        "get_tasks": get_tasks,
        "get_task": get_task,
        "download": download_roster,
        "update": update_roster,
        "list": list_available_rosters,
        "start": start,
        "changelog": changelog,
        "--version": version,
    }

    fire.Fire(commands, command=args if argv is not None else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
