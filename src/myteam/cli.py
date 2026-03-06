"""Command-line interface for the myteam package."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import fire
from myteam.utils import is_role_dir, is_skill_dir

from . import __version__
from .rosters import download_roster, list_available_rosters
from .templates import get_template

APP_NAME = "myteam"
AGENTS_DIRNAME = ".myteam"
ENCODING = "utf-8"


def _base() -> Path:
    """Return the directory from which the CLI was invoked."""
    return Path.cwd()


def _agents_root(base: Path) -> Path:
    return base / AGENTS_DIRNAME


def _role_dir(base: Path, role: str) -> Path:
    return _agents_root(base) / role


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_py_script(path: Path, contents: str):
    path.write_text(contents, encoding=ENCODING)
    # path.chmod(path.stat().st_mode | 0o111)


def _new_dir(base: Path, dir_type: str, name_parts: list[str], instruction_text: str, load_text: str):
    name_dir = base.joinpath(*name_parts)
    name = '/'.join(name_parts)
    if name_dir.exists():
        print(f"{dir_type.title()} '{name}' already exists at {name_dir}", file=sys.stderr)
        exit(1)

    _ensure_dir(name_dir)
    (name_dir / (dir_type + ".md")).write_text(instruction_text, encoding=ENCODING)
    _write_py_script(name_dir / "load.py", load_text)


def init():
    """Initialize the myteam directory with default role."""
    _new_dir(_base(), 'role', ['.myteam'],
             '',  # default role doesn't come with instructions
             get_template('role_load_template.py')
             )

    # Create AGENTS.md with onboarding instructions.
    agents_md = _base() / "AGENTS.md"
    if not agents_md.exists():
        agents_md.write_text(get_template('agents_md_template.md'), encoding=ENCODING)


def new_role(role: str):
    """Create a new role directory with placeholder files."""
    _new_dir(_agents_root(_base()), 'role', role.split('/'),
             get_template('role_definition_template.md'),
             get_template('role_load_template.py')
             )


def new_skill(skill: str):
    _new_dir(_agents_root(_base()), 'skill', skill.split('/'),
             get_template('skill_definition_template.md'),
             get_template('skill_load_template.py')
             )


def remove(name: str):
    """Delete the directory for a role or skill if it exists."""
    role_dir = _role_dir(_base(), name)  # TODO fix for skills
    if not role_dir.exists():
        print(f"'{name}' not found at {role_dir}", file=sys.stderr)
        exit(1)

    if not role_dir.is_dir():
        print(f"Path for '{name}' is not a directory: {role_dir}", file=sys.stderr)
        exit(1)

    try:
        shutil.rmtree(role_dir)
    except OSError as exc:
        print(f"Failed to remove '{name}': {exc}", file=sys.stderr)
        exit(1)


def _get_name(dir_type: str, name_dir: Path, name: str):
    if not name_dir.exists():
        print(f"{dir_type.title()} '{name}' not found. Run 'myteam new {dir_type} {name}' to create it.",
              file=sys.stderr)
        exit(1)

    load_py = name_dir / "load.py"
    if not load_py.exists():
        print(f"No load.py found for {dir_type} '{name}'.", file=sys.stderr)
        exit(1)

    try:
        # TODO - support venv when available
        result = subprocess.run([sys.executable, str(load_py)], cwd=name_dir, check=False)
        exit(result.returncode)

    except OSError as exc:
        print(f"Failed to execute load.py for {dir_type} '{name}': {exc}", file=sys.stderr)
        exit(1)


def get_role(role: str = None):
    """Print the instructions for the given role if available."""
    folder = _agents_root(_base())
    if role is not None:
        folder = folder.joinpath(*role.split('/'))

    if not is_role_dir(folder):
        print(f'Not a role: {role}', file=sys.stderr)
        exit(1)
    _get_name('role', folder, role)


def get_skill(skill: str):
    """Print the instructions for the given skill if available."""
    folder = _agents_root(_base()).joinpath(*skill.split('/'))
    if not is_skill_dir(folder):
        print(f'Not a skill: {skill}', file=sys.stderr)
        exit(1)
    _get_name('skill', folder, skill)


def version() -> str:
    return f"{APP_NAME} {__version__}"


def main(argv: list[str] | None = None):
    commands = {
        "init": init,
        "new": {
            "role": new_role,
            "skill": new_skill
        },
        "remove": remove,
        "get": {
            "role": get_role,
            "skill": get_skill,
        },
        "download-roster": download_roster,
        "list-rosters": list_available_rosters,
        "--version": version,
    }

    fire.Fire(commands)


if __name__ == "__main__":
    sys.exit(main())
