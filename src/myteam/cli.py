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
from .workflow.execution.cli_commands import (
    workflow_result as workflow_result_command,
    workflow_start as workflow_start_command,
)


def _run_workflow_start_cli(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="myteam workflow-start")
    parser.add_argument("workflow")
    parser.add_argument("--session-nonce", required=True)
    parser.add_argument("--json")
    parser.add_argument("--text")
    args = parser.parse_args(argv)
    workflow_start_command(
        args.workflow,
        json=args.json,
        text=args.text,
        session_nonce=args.session_nonce,
    )


def _run_workflow_result_cli(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="myteam workflow-result")
    parser.add_argument("--session-nonce", required=True)
    parser.add_argument("--json")
    parser.add_argument("--text")
    args = parser.parse_args(argv)
    workflow_result_command(
        json=args.json,
        text=args.text,
        session_nonce=args.session_nonce,
    )


def main(argv: list[str] | None = None):
    args = sys.argv[1:] if argv is None else list(argv)
    if args[:1] == ["workflow-start"]:
        _run_workflow_start_cli(args[1:])
        return 0
    if args[:1] == ["workflow-result"]:
        _run_workflow_result_cli(args[1:])
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
        "workflow-result": workflow_result_command,
        "workflow-start": workflow_start_command,
        "changelog": changelog,
        "--version": version,
    }

    fire.Fire(commands, command=args if argv is not None else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
