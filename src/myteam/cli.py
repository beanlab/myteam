"""Command-line interface for the myteam package."""
from __future__ import annotations

import sys
import argparse
import shutil
import subprocess
from importlib import resources
from pathlib import Path

from . import __version__

APP_NAME = "myteam"
DEFAULT_ROLE = "main"
AGENTS_DIRNAME = ".agents"


def _main_agent_script() -> str:
    """Load the embedded agent template from package data."""
    return resources.files(__package__).joinpath("main_agent_template.py").read_text(encoding="utf-8")


def _main_instructions_template() -> str:
    """Load the default main-role instructions template."""
    return resources.files(__package__).joinpath("main_instructions_template.md").read_text(encoding="utf-8")


def _main_info_template() -> str:
    """Load the default main-role info template."""
    return resources.files(__package__).joinpath("main_info_template.md").read_text(encoding="utf-8")


def _role_agent_script() -> str:
    """Load the generic role agent template."""
    return resources.files(__package__).joinpath("role_agent_template.py").read_text(encoding="utf-8")


def _agents_root(base: Path) -> Path:
    return base / AGENTS_DIRNAME


def _role_dir(base: Path, role: str) -> Path:
    return _agents_root(base) / role


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def cmd_init(base: Path) -> int:
    """Initialize the myteam directory with default main role."""
    agents_dir = _agents_root(base)
    _ensure_dir(agents_dir)

    # Create AGENTS.md with onboarding instructions.
    agents_md = base / "AGENTS.md"
    if not agents_md.exists():
        agents_md.write_text(
            "Run `myteam get-role <role>` with your role. If you have no role, assume your role is `main`.\n",
            encoding="utf-8",
        )

    # Create default main role.
    main_dir = _role_dir(base, DEFAULT_ROLE)
    _ensure_dir(main_dir)

    info = main_dir / "info.md"
    if not info.exists():
        info.write_text(_main_info_template(), encoding="utf-8")
    instructions = main_dir / "instructions.md"
    if not instructions.exists():
        instructions.write_text(_main_instructions_template(), encoding="utf-8")
    agent_py = main_dir / "agent.py"
    if not agent_py.exists():
        agent_py.write_text(_main_agent_script(), encoding="utf-8")
        agent_py.chmod(agent_py.stat().st_mode | 0o111)

    return 0


def cmd_new(base: Path, role: str) -> int:
    """Create a new role directory with placeholder files."""
    role_dir = _role_dir(base, role)
    if role_dir.exists():
        print(f"Role '{role}' already exists at {role_dir}", file=sys.stderr)
        return 1

    _ensure_dir(role_dir)
    (role_dir / "info.md").write_text("", encoding="utf-8")
    (role_dir / "instructions.md").write_text("", encoding="utf-8")
    agent_py = role_dir / "agent.py"
    agent_py.write_text(_role_agent_script(), encoding="utf-8")
    agent_py.chmod(agent_py.stat().st_mode | 0o111)
    return 0


def cmd_remove(base: Path, role: str) -> int:
    """Delete the directory for a role if it exists."""
    role_dir = _role_dir(base, role)
    if not role_dir.exists():
        print(f"Role '{role}' not found at {role_dir}", file=sys.stderr)
        return 1

    if not role_dir.is_dir():
        print(f"Path for role '{role}' is not a directory: {role_dir}", file=sys.stderr)
        return 1

    try:
        shutil.rmtree(role_dir)
    except OSError as exc:
        print(f"Failed to remove role '{role}': {exc}", file=sys.stderr)
        return 1

    return 0


def cmd_get_role(base: Path, role: str) -> int:
    """Print the instructions for the given role if available."""
    role_dir = _role_dir(base, role)
    if not role_dir.exists():
        print(f"Role '{role}' not found. Run 'myteam new {role}' to create it.", file=sys.stderr)
        return 1

    agent_py = role_dir / "agent.py"
    if agent_py.exists():
        try:
            result = subprocess.run([sys.executable, str(agent_py)], cwd=role_dir, check=False)
        except OSError as exc:
            print(f"Failed to execute agent.py for role '{role}': {exc}", file=sys.stderr)
            return 1
        return result.returncode

    print(f"No agent.py found for role '{role}'.", file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=APP_NAME, description="Manage agent roster roles.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Initialize roster with default files.")

    new_parser = sub.add_parser("new", help="Create a new role.")
    new_parser.add_argument("role", help="Role name to create.")

    remove_parser = sub.add_parser("remove", help="Delete an existing role.")
    remove_parser.add_argument("role", help="Role name to delete.")

    get_role_parser = sub.add_parser("get-role", help="Print instructions for a role.")
    get_role_parser.add_argument("role", nargs="?", default=DEFAULT_ROLE, help="Role name (default: main).")

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    base = Path.cwd()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        return cmd_init(base)
    if args.command == "new":
        return cmd_new(base, args.role)
    if args.command == "remove":
        return cmd_remove(base, args.role)
    if args.command == "get-role":
        return cmd_get_role(base, args.role)

    parser.error("Unknown command")
    return 1


if __name__ == "__main__":
    sys.exit(main())
