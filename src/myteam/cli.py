"""Command-line interface for the myteam package."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from importlib import resources
from pathlib import Path
from typing import Callable

import fire

from . import __version__

APP_NAME = "myteam"
DEFAULT_ROLE = "main"
AGENTS_DIRNAME = ".myteam"
ENCODING = "utf-8"
ROSTER_REPOSITORY_URL = "https://api.github.com/repos/beanlab/rosters/git/trees"
ROSTER_RAW_BASE_URL = "https://raw.githubusercontent.com/beanlab/rosters/refs/heads/main"
ZIP_FILE_NAME = "roster.zip"


def _base() -> Path:
    """Return the directory from which the CLI was invoked."""
    return Path.cwd()


def _main_agent_script() -> str:
    """Load the embedded agent template from package data."""
    return resources.files(__package__).joinpath("main_agent_template.py").read_text(encoding=ENCODING)


def _main_instructions_template() -> str:
    """Load the default main-role instructions template."""
    return resources.files(__package__).joinpath("main_instructions_template.md").read_text(encoding=ENCODING)


def _role_agent_script() -> str:
    """Load the generic role agent template."""
    return resources.files(__package__).joinpath("role_agent_template.py").read_text(encoding=ENCODING)


def _agents_md_template() -> str:
    return resources.files(__package__).joinpath("agents_md_template.md").read_text(encoding=ENCODING)


def _agents_root() -> Path:
    return _base() / AGENTS_DIRNAME


def _role_dir(role: str) -> Path:
    return _agents_root() / role


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_agent_py_script(path: Path, contents: str):
    path.write_text(contents, encoding=ENCODING)
    path.chmod(path.stat().st_mode | 0o111)


def init():
    """Initialize the myteam directory with default main role."""
    agents_dir = _agents_root(_base())
    _ensure_dir(agents_dir)

    # Create AGENTS.md with onboarding instructions.
    agents_md = _base() / "AGENTS.md"
    if not agents_md.exists():
        agents_md.write_text(_agents_md_template(), encoding=ENCODING)

    # Create default main role.
    main_dir = _role_dir(DEFAULT_ROLE)
    _ensure_dir(main_dir)

    instructions = main_dir / "instructions.md"
    if not instructions.exists():
        instructions.write_text(_main_instructions_template(), encoding=ENCODING)
    agent_py = main_dir / "agent.py"
    if not agent_py.exists():
        _write_agent_py_script(agent_py, _main_agent_script())


def new(role: str):
    """Create a new role directory with placeholder files."""
    role_dir = _role_dir(role)
    if role_dir.exists():
        print(f"Role '{role}' already exists at {role_dir}", file=sys.stderr)
        exit(1)

    _ensure_dir(role_dir)
    (role_dir / "info.md").write_text("", encoding=ENCODING)
    (role_dir / "instructions.md").write_text("", encoding=ENCODING)
    agent_py = role_dir / "agent.py"
    _write_agent_py_script(agent_py, _role_agent_script())


def remove(role: str):
    """Delete the directory for a role if it exists."""
    role_dir = _role_dir(role)
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


def get_role(role: str):
    """Print the instructions for the given role if available."""
    role_dir = _role_dir(role)
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


def _fetch_json(url: str) -> dict:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": APP_NAME})
        with urllib.request.urlopen(request) as response:
            return json.load(response)
    except Exception as exc:
        print(f"Failed to fetch JSON from {url}: {exc}", file=sys.stderr)
        exit(1)


def _download_file(url: str, output_path: Path):
    try:
        request = urllib.request.Request(url, headers={"User-Agent": APP_NAME})
        with urllib.request.urlopen(request) as response:
            data = response.read()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)
    except Exception as exc:
        print(f"Failed to download file from {url}: {exc}", file=sys.stderr)
        exit(1)


def _fetch_available_rosters():
    root_tree = _fetch_json(ROSTER_REPOSITORY_URL + "/main?recursive=1")
    trees =  root_tree.get("tree", [])
    # return [tree for tree in trees if tree.get('type') == "tree"]
    return trees


def _fetch_roster_tree(roster: str):
    roster_trees = _fetch_available_rosters()
    roster_tree = next(
        (entry for entry in roster_trees if entry.get("path") == roster),
        None,
    )
    if roster_tree is None:
        _handle_missing_roster(roster, roster_trees)

    return roster_tree


def _handle_missing_roster(roster: str, roster_trees: list):
    roster_names = [entry.get("path") for entry in roster_trees if entry.get("type") == "tree"]
    roster_names.sort()
    available = ", ".join(roster_names) if roster_names else "none"
    print(f"Roster '{roster}' not found. Available rosters: {available}", file=sys.stderr)
    exit(1)


def _fetch_tree_files(roster_tree):
    subtree_url = f"{ROSTER_REPOSITORY_URL}/{roster_tree['sha']}?recursive=1"
    subtree = _fetch_json(subtree_url)
    file_entries = [entry for entry in subtree.get("tree", []) if entry.get("type") == "blob"]
    if not file_entries:
        print(f"No files found in roster '{roster_tree.get('path')}'.", file=sys.stderr)
        exit(1)

    return file_entries


def _download_tree_files(file_entries: list, tree_path: str, destination: Path):
    total = len(file_entries)
    base = _base()
    for idx, entry in enumerate(file_entries, start=1):
        rel_path = entry.get("path")
        if not rel_path:
            continue
        raw_url = f"{ROSTER_RAW_BASE_URL}/{tree_path}/{rel_path}"
        print(f"\rDownloading {tree_path} {idx}/{total}", end="", file=sys.stderr)
        _download_file(raw_url, destination / rel_path)
    print("", file=sys.stderr)


def download(download_path: str, relative_destination: str = AGENTS_DIRNAME):
    destination = _base() / relative_destination
    roster_tree = _fetch_roster_tree(download_path)

    if roster_tree.get('type') == 'blob':
        file_name = roster_tree.get('path').split("/")[-1]
        _download_file(f"{ROSTER_RAW_BASE_URL}/{roster_tree.get('path')}", destination / file_name)
    else:
        tree_files = _fetch_tree_files(roster_tree)
        _download_tree_files(tree_files, download_path, destination)


def list_available_items():
    available_rosters = _fetch_available_rosters()
    roster_names = [roster.get('path') for roster in available_rosters]
    for name in roster_names:
        print(name)


def version() -> str:
    return f"{APP_NAME} {__version__}"


def main(argv: list[str] | None = None):
    commands = {
        "init": init,
        "new": new,
        "remove": remove,
        "get-role": get_role,
        "download": download,
        "list": list_available_items,
        "--version": version,
    }

    fire.Fire(commands)


if __name__ == "__main__":
    sys.exit(main())
