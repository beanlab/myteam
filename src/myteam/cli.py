"""Command-line interface for the myteam package."""
from __future__ import annotations

import sys
import shutil
import subprocess
from importlib import resources
from pathlib import Path

import fire

from . import __version__

APP_NAME = "myteam"
DEFAULT_ROLE = "main"
AGENTS_DIRNAME = ".myteam"


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


def _write_agent_py_script(path: Path, contents: str):
    path.write_text(contents, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def init() -> int:
    """Initialize the myteam directory with default main role."""
    agents_dir = _agents_root(_base())
    _ensure_dir(agents_dir)

    # Create AGENTS.md with onboarding instructions.
    agents_md = _base() / "AGENTS.md"
    if not agents_md.exists():
        agents_md.write_text(
            "Run `myteam get-role <role>` with your role. If you have no role, assume your role is `main`.\n",
            encoding="utf-8",
        )

    # Create default main role.
    main_dir = _role_dir(_base(), DEFAULT_ROLE)
    _ensure_dir(main_dir)

    info = main_dir / "info.md"
    if not info.exists():
        info.write_text(_main_info_template(), encoding="utf-8")
    instructions = main_dir / "instructions.md"
    if not instructions.exists():
        instructions.write_text(_main_instructions_template(), encoding="utf-8")
    agent_py = main_dir / "agent.py"
    if not agent_py.exists():
        _write_agent_py_script(agent_py, _main_agent_script())


def new(role: str) -> int:
    """Create a new role directory with placeholder files."""
    role_dir = _role_dir(_base(), role)
    if role_dir.exists():
        print(f"Role '{role}' already exists at {role_dir}", file=sys.stderr)
        exit(1)

    _ensure_dir(role_dir)
    (role_dir / "info.md").write_text("", encoding="utf-8")
    (role_dir / "instructions.md").write_text("", encoding="utf-8")
    agent_py = role_dir / "agent.py"
    _write_agent_py_script(agent_py, _role_agent_script())


def remove(role: str) -> int:
    """Delete the directory for a role if it exists."""
    role_dir = _role_dir(_base(), role)
    if not role_dir.exists():
        print(f"Role '{role}' not found at {role_dir}", file=sys.stderr)
        exit(1)

    if not role_dir.is_dir():
        print(f"Path for role '{role}' is not a directory: {role_dir}", file=sys.stderr)
        exit(1)

    try:
        shutil.rmtree(role_dir)
    except OSError as exc:
        print(f"Failed to remove role '{role}': {exc}", file=sys.stderr)
        exit(1)


def get_role(role: str) -> int:
    """Print the instructions for the given role if available."""
    role_dir = _role_dir(_base(), role)
    if not role_dir.exists():
        print(f"Role '{role}' not found. Run 'myteam new {role}' to create it.", file=sys.stderr)
        exit(1)

    agent_py = role_dir / "agent.py"
    if agent_py.exists():
        try:
            result = subprocess.run([sys.executable, str(agent_py)], cwd=role_dir, check=False)
        except OSError as exc:
            print(f"Failed to execute agent.py for role '{role}': {exc}", file=sys.stderr)
            exit(1)
        exit(result.returncode)

    print(f"No agent.py found for role '{role}'.", file=sys.stderr)
    exit(1)


def _base() -> Path:
    """Return the directory from which the CLI was invoked."""
    return Path.cwd()


def version() -> str:
    return f"{APP_NAME} {__version__}"


def main(argv: list[str] | None = None) -> int:
    commands = {
        "init": init,
        "new": new,
        "remove": remove,
        "get-role": get_role,
        "--version": version,
    }

    fire.Fire(commands)


if __name__ == "__main__":
    sys.exit(main())
