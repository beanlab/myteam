"""Command-line interface for the myteam package."""
from __future__ import annotations

import sys
import shutil
import subprocess
from importlib import resources
from pathlib import Path
import requests

import fire

from . import __version__

APP_NAME = "myteam"
DEFAULT_ROLE = "main"
AGENTS_DIRNAME = ".myteam"
ENCODING = "utf-8"
DEFAULT_REPO = "OWNER/REPO"


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


def _agents_root(base: Path) -> Path:
    return base / AGENTS_DIRNAME


def _role_dir(base: Path, role: str) -> Path:
    return _agents_root(base) / role


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_agent_py_script(path: Path, contents: str):
    path.write_text(contents, encoding=ENCODING)
    path.chmod(path.stat().st_mode | 0o111)


def init() -> int:
    """Initialize the myteam directory with default main role."""
    agents_dir = _agents_root(_base())
    _ensure_dir(agents_dir)

    # Create AGENTS.md with onboarding instructions.
    agents_md = _base() / "AGENTS.md"
    if not agents_md.exists():
        agents_md.write_text(_agents_md_template(), encoding=ENCODING)

    # Create default main role.
    main_dir = _role_dir(_base(), DEFAULT_ROLE)
    _ensure_dir(main_dir)

    instructions = main_dir / "instructions.md"
    if not instructions.exists():
        instructions.write_text(_main_instructions_template(), encoding=ENCODING)
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
    (role_dir / "info.md").write_text("", encoding=ENCODING)
    (role_dir / "instructions.md").write_text("", encoding=ENCODING)
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


def _github_contents(repo: str, path: str, ref: str) -> list[dict] | dict:
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json"}
    r = requests.get(url, headers=headers, params={"ref": ref}, timeout=30)
    if r.status_code != 200:
        raise SystemExit(f"Failed to fetch metadata for {path} from {repo}@{ref}: {r.status_code} {r.text}")
    return r.json()


def _download_file(url: str, target: Path) -> None:
    r = requests.get(url, timeout=30)
    if r.status_code != 200:
        raise SystemExit(f"Failed to download {url}: {r.status_code} {r.text}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise SystemExit(f"Target file already exists: {target}")
    target.write_bytes(r.content)


def _download_dir(repo: str, path: str, ref: str, target_root: Path) -> None:
    entries = _github_contents(repo, path, ref)
    if not isinstance(entries, list):
        raise SystemExit(f"Expected directory at {path}, got a file instead.")
    for entry in entries:
        entry_type = entry.get("type")
        entry_path = entry.get("path")
        if not entry_path:
            continue
        relative = Path(entry_path).relative_to(path)
        target = target_root / relative
        if entry_type == "dir":
            _download_dir(repo, entry_path, ref, target_root)
        elif entry_type == "file":
            download_url = entry.get("download_url")
            if not download_url:
                raise SystemExit(f"Missing download_url for {entry_path}")
            _download_file(download_url, target)
        else:
            raise SystemExit(f"Unsupported entry type '{entry_type}' for {entry_path}")


def download_role(path: str, repo: str = DEFAULT_REPO, ref: str = "main", dest: str | None = None) -> int:
    """Download a file or directory from GitHub and save it into the project."""
    meta = _github_contents(repo, path, ref)
    target_root = Path(dest or path)
    if isinstance(meta, list):
        if target_root.exists():
            raise SystemExit(f"Target directory already exists: {target_root}")
        target_root.mkdir(parents=True, exist_ok=True)
        _download_dir(repo, path, ref, target_root)
        return 0
    if meta.get("type") != "file":
        raise SystemExit(f"Unsupported path type at {path}: {meta.get('type')}")
    download_url = meta.get("download_url")
    if not download_url:
        raise SystemExit(f"Missing download_url for {path}")
    _download_file(download_url, target_root)
    return 0


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
        "download-role": download_role,
    }

    fire.Fire(commands)


if __name__ == "__main__":
    sys.exit(main())
