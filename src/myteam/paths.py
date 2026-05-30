"""Path helpers and constants for the myteam CLI."""
from __future__ import annotations

from pathlib import Path

APP_NAME = "myteam"
DEFAULT_LOCAL_ROOT = ".myteam"
AGENTS_DIRNAME = DEFAULT_LOCAL_ROOT
BUILTIN_ROOT_NAME = "builtins"
ENCODING = "utf-8"
SUPPORTED_TASK_SUFFIXES = {".py", ".md", ".yaml", ".yml"}
TASK_SUFFIX_PRIORITY = (".py", ".md", ".yaml", ".yml")
NON_TASK_FILES = {"info.md", "load.py", "readme.md", "role.md", "skill.md", ".config.yaml"}


def base_dir() -> Path:
    """Return the directory from which the CLI was invoked."""
    return Path.cwd()


def normalize_local_root(prefix: str | Path | None = None) -> Path:
    raw_prefix = Path(DEFAULT_LOCAL_ROOT if prefix is None else prefix)
    if raw_prefix.is_absolute():
        raise ValueError("Local root prefix must be a relative path.")
    return raw_prefix


def agents_root(base: Path, prefix: str | Path | None = None) -> Path:
    return base / normalize_local_root(prefix)


def builtin_agents_root() -> Path:
    return Path(__file__).resolve().parent / "builtins"


def role_dir(base: Path, role: str, prefix: str | Path | None = None) -> Path:
    return agents_root(base, prefix) / role


def task_candidates(base: Path, task: str, prefix: str | Path | None = None) -> list[Path]:
    root = agents_root(base, prefix)
    requested_path = root.joinpath(*task.split("/"))
    candidates: list[Path] = []

    if requested_path.suffix:
        if requested_path.suffix not in SUPPORTED_TASK_SUFFIXES:
            raise ValueError(f"Task '{task}' has unsupported extension '{requested_path.suffix}'.")
        if requested_path.is_file():
            candidates.append(requested_path)
        return candidates

    for suffix in TASK_SUFFIX_PRIORITY:
        candidate = requested_path.with_suffix(suffix)
        if candidate.is_file():
            candidates.append(candidate)
    return candidates


def task_path(base: Path, task: str, prefix: str | Path | None = None) -> Path:
    candidates = task_candidates(base, task, prefix)
    if not candidates:
        raise ValueError(f"Task '{task}' not found.")
    return candidates[0]
