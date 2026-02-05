"""Command-line interface for the myteam package."""
from __future__ import annotations

import sys
import argparse
import shutil
from pathlib import Path

from . import __version__

APP_NAME = "myteam"
DEFAULT_ROLE = "main"
AGENTS_DIRNAME = ".agents"


def _agents_root(base: Path) -> Path:
    return base / AGENTS_DIRNAME


def _role_dir(base: Path, role: str) -> Path:
    return _agents_root(base) / role


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def cmd_init(base: Path) -> int:
    """Initialize the myteam directory with default developer role."""
    agents_dir = _agents_root(base)
    _ensure_dir(agents_dir)

    # Create AGENTS.md with onboarding instructions.
    agents_md = base / "AGENTS.md"
    if not agents_md.exists():
        agents_md.write_text(
            "Run `myteam whoami <role>` with your role. If you have no role, assume your role is `main`.\n",
            encoding="utf-8",
        )

    # Create default developer role.
    developer_dir = _role_dir(base, "developer")
    _ensure_dir(developer_dir)

    (developer_dir / "info.md").touch(exist_ok=True)
    instructions = developer_dir / "instructions.md"
    if not instructions.exists():
        instructions.write_text("Provide developer-specific instructions here.\n", encoding="utf-8")

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


def cmd_whoami(base: Path, role: str) -> int:
    """Print the instructions for the given role if available."""
    role_dir = _role_dir(base, role)
    if not role_dir.exists():
        print(f"Role '{role}' not found. Run 'myteam new {role}' to create it.", file=sys.stderr)
        return 1

    agent_py = role_dir / "agent.py"
    if agent_py.exists():
        # For now, we simply notify; executing arbitrary code is avoided.
        print(f"agent.py found at {agent_py}; execution not implemented.")
        return 0

    instructions = role_dir / "instructions.md"
    if instructions.exists():
        print(instructions.read_text(encoding="utf-8"))
        return 0

    print(f"No instructions found for role '{role}'.", file=sys.stderr)
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

    who_parser = sub.add_parser("whoami", help="Print instructions for a role.")
    who_parser.add_argument("role", nargs="?", default=DEFAULT_ROLE, help="Role name (default: main).")

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
    if args.command == "whoami":
        return cmd_whoami(base, args.role)

    parser.error("Unknown command")
    return 1


if __name__ == "__main__":
    sys.exit(main())
