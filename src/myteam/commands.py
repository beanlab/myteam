"""Command implementations for the myteam CLI."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .disclosure import PROJECT_ROOT_ENV_VAR, builtin_skill_dir, is_role_dir, is_skill_dir

from . import __version__
from .paths import APP_NAME, BUILTIN_ROOT_NAME, DEFAULT_LOCAL_ROOT, ENCODING, agents_root, base_dir, role_dir
from .rosters import download_roster, list_available_rosters, update_roster
from .templates import get_template
from .upgrade import write_tracked_version


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_py_script(path: Path, contents: str) -> None:
    path.write_text(contents, encoding=ENCODING)


def _selected_root(prefix: str | None) -> Path:
    try:
        return agents_root(base_dir(), prefix)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)


def new_dir(
    base: Path,
    dir_type: str,
    name_parts: list[str],
    instruction_text: str,
    load_text: str,
) -> None:
    name_dir = base.joinpath(*name_parts)
    name = "/".join(name_parts)
    if name_dir.exists():
        print(f"{dir_type.title()} '{name}' already exists at {name_dir}", file=sys.stderr)
        raise SystemExit(1)

    ensure_dir(name_dir)
    (name_dir / f"{dir_type}.md").write_text(instruction_text, encoding=ENCODING)
    write_py_script(name_dir / "load.py", load_text)


def init(prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    """Initialize the myteam directory with default role."""
    root = _selected_root(prefix)
    new_dir(
        base_dir(),
        "role",
        list(root.relative_to(base_dir()).parts),
        "",
        get_template("root_role_load_template.py"),
    )
    write_tracked_version(root)

    agents_md = base_dir() / "AGENTS.md"
    if not agents_md.exists():
        agents_md.write_text(get_template("agents_md_template.md"), encoding=ENCODING)


def new_role(role: str, prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    """Create a new role directory with placeholder files."""
    new_dir(
        _selected_root(prefix),
        "role",
        role.split("/"),
        get_template("role_definition_template.md"),
        get_template("role_load_template.py"),
    )


def new_skill(skill: str, prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    if skill == BUILTIN_ROOT_NAME or skill.startswith(f"{BUILTIN_ROOT_NAME}/"):
        print(f"Skill path '{skill}' uses the reserved built-in namespace '{BUILTIN_ROOT_NAME}'.", file=sys.stderr)
        raise SystemExit(1)
    new_dir(
        _selected_root(prefix),
        "skill",
        skill.split("/"),
        get_template("skill_definition_template.md"),
        get_template("skill_load_template.py"),
    )


def remove(name: str, prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    """Delete the directory for a role or skill if it exists."""
    target_dir = role_dir(base_dir(), name, prefix)  # TODO fix for skills
    if not target_dir.exists():
        print(f"'{name}' not found at {target_dir}", file=sys.stderr)
        raise SystemExit(1)

    if not target_dir.is_dir():
        print(f"Path for '{name}' is not a directory: {target_dir}", file=sys.stderr)
        raise SystemExit(1)

    try:
        shutil.rmtree(target_dir)
    except OSError as exc:
        print(f"Failed to remove '{name}': {exc}", file=sys.stderr)
        raise SystemExit(1)


def get_name(dir_type: str, name_dir: Path, name: str | None, *, project_root: Path) -> None:
    if not name_dir.exists():
        print(
            f"{dir_type.title()} '{name}' not found. Run 'myteam new {dir_type} {name}' to create it.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    load_py = name_dir / "load.py"
    if not load_py.exists():
        print(f"No load.py found for {dir_type} '{name}'.", file=sys.stderr)
        raise SystemExit(1)

    try:
        env = dict(os.environ)
        env[PROJECT_ROOT_ENV_VAR] = str(project_root)
        result = subprocess.run([sys.executable, str(load_py)], cwd=name_dir, env=env, check=False)
        raise SystemExit(result.returncode)
    except OSError as exc:
        print(f"Failed to execute load.py for {dir_type} '{name}': {exc}", file=sys.stderr)
        raise SystemExit(1)


def get_role(role: str | None = None, prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    """Print the instructions for the given role if available."""
    project_root = _selected_root(prefix)
    folder = project_root
    if role is not None:
        folder = folder.joinpath(*role.split("/"))

    if not is_role_dir(folder):
        print(f"Not a role: {role}", file=sys.stderr)
        raise SystemExit(1)
    get_name("role", folder, role, project_root=project_root)


def get_skill(skill: str, prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    """Print the instructions for the given skill if available."""
    project_root = _selected_root(prefix)
    if skill == BUILTIN_ROOT_NAME or skill.startswith(f"{BUILTIN_ROOT_NAME}/"):
        folder = builtin_skill_dir(skill)
        if not is_skill_dir(folder):
            print(f"Not a skill: {skill}", file=sys.stderr)
            raise SystemExit(1)
        get_name("skill", folder, skill, project_root=project_root)

    folder = project_root.joinpath(*skill.split("/"))
    if is_skill_dir(folder):
        get_name("skill", folder, skill, project_root=project_root)
    print(f"Not a skill: {skill}", file=sys.stderr)
    raise SystemExit(1)


def version() -> str:
    return f"{APP_NAME} {__version__}"


__all__ = [
    "download_roster",
    "get_role",
    "get_skill",
    "init",
    "list_available_rosters",
    "new_role",
    "new_skill",
    "remove",
    "update_roster",
    "version",
]
