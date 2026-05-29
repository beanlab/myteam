"""Path helpers and constants for the myteam CLI."""
from __future__ import annotations

from pathlib import Path

APP_NAME = "myteam"
DEFAULT_LOCAL_ROOT = ".myteam"
AGENTS_DIRNAME = DEFAULT_LOCAL_ROOT
BUILTIN_ROOT_NAME = "builtins"
ENCODING = "utf-8"
SUPPORTED_WORKFLOW_SUFFIXES = {".py", ".yaml", ".yml"}
WORKFLOW_SUFFIX_PRIORITY = (".py", ".yaml", ".yml")


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


def workflow_candidates(base: Path, workflow: str, prefix: str | Path | None = None) -> list[Path]:
    root = agents_root(base, prefix)
    requested_path = root.joinpath(*workflow.split("/"))
    candidates: list[Path] = []

    if requested_path.suffix:
        if requested_path.suffix not in SUPPORTED_WORKFLOW_SUFFIXES:
            raise ValueError(f"Workflow '{workflow}' has unsupported extension '{requested_path.suffix}'.")
        if requested_path.is_file():
            candidates.append(requested_path)
        return candidates

    for suffix in WORKFLOW_SUFFIX_PRIORITY:
        candidate = requested_path.with_suffix(suffix)
        if candidate.is_file():
            candidates.append(candidate)
    return candidates


def workflow_path(base: Path, workflow: str, prefix: str | Path | None = None) -> Path:
    candidates = workflow_candidates(base, workflow, prefix)
    if not candidates:
        raise ValueError(f"Workflow '{workflow}' not found.")
    return candidates[0]
