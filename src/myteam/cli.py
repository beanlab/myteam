"""Command-line interface wiring for the myteam package."""
from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import Any

from .commands import changelog, onboard, version
from .explain import explain_resources
from .listing import list_resources
from .skills import load_skill, new_skill
from .workflows import new_workflow, report_result, start_workflow_cli
from .workflows.where import where_cli


def _print_result(function: Callable[..., str], *args: Any, **kwargs: Any):
    print(function(*args, **kwargs), end="")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="myteam")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("explain")

    list_parser = commands.add_parser("list")
    list_parser.add_argument("-d", "--directory", action="store_true")
    list_parser.add_argument("targets", nargs="*")

    new_parser = commands.add_parser("new")
    resource_types = new_parser.add_subparsers(dest="resource_type", required=True)
    for resource_type in ("skill", "workflow"):
        resource_parser = resource_types.add_parser(resource_type)
        resource_parser.add_argument("name")
        resource_parser.add_argument("--parents", action="store_true")

    load_parser = commands.add_parser("load")
    load_parser.add_argument("skill")

    commands.add_parser("onboard")
    commands.add_parser("where")

    start_parser = commands.add_parser("start")
    start_parser.add_argument("--input")
    start_parser.add_argument("workflow")
    start_parser.add_argument("workflow_args", nargs=argparse.REMAINDER)

    result_parser = commands.add_parser("result")
    result_parser.add_argument("result_json", nargs="?")

    commands.add_parser("version")
    commands.add_parser("changelog")
    return parser


def _dispatch(args: argparse.Namespace):
    if args.command == "explain":
        _print_result(explain_resources)
    elif args.command == "list":
        _print_result(list_resources, *args.targets, directory=args.directory)
    elif args.command == "new":
        creator = new_skill if args.resource_type == "skill" else new_workflow
        creator(args.name, parents=args.parents)
    elif args.command == "load":
        _print_result(load_skill, args.skill)
    elif args.command == "onboard":
        _print_result(onboard)
    elif args.command == "start":
        start_workflow_cli(args.workflow, *args.workflow_args, input=args.input)
    elif args.command == "where":
        where_cli()
    elif args.command == "result":
        report_result(args.result_json)
    elif args.command == "version":
        _print_result(version)
    elif args.command == "changelog":
        _print_result(changelog)


def _parse_args() -> argparse.Namespace:
    parser = _build_parser()
    args, remaining = parser.parse_known_args()
    if args.command == "list" and all(not value.startswith("-") for value in remaining):
        args.targets.extend(remaining)
    elif remaining:
        parser.error(f"unrecognized arguments: {' '.join(remaining)}")
    return args


def main():
    _dispatch(_parse_args())


if __name__ == "__main__":
    main()
