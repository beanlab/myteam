"""Path helpers and constants for the myteam CLI."""
from __future__ import annotations

from pathlib import Path

APP_NAME = "myteam"
DEFAULT_LOCAL_ROOT = ".myteam"
AGENTS_DIRNAME = DEFAULT_LOCAL_ROOT
BUILTIN_ROOT_NAME = "builtins"
ENCODING = "utf-8"


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

    if requested_path.suffix in {".yaml", ".yml", ".py"}:
        if requested_path.exists():
            candidates.append(requested_path)
        return candidates

    for suffix in (".yaml", ".yml", ".py"):
        candidate = requested_path.with_suffix(suffix)
        if candidate.exists():
            candidates.append(candidate)
    return candidates


def workflow_path(base: Path, workflow: str, prefix: str | Path | None = None) -> Path:
    candidates = workflow_candidates(base, workflow, prefix)
    if not candidates:
        raise ValueError(f"Workflow '{workflow}' not found.")
    if len(candidates) > 1:
        matches = ", ".join(str(path) for path in candidates)
        raise ValueError(f"Workflow '{workflow}' is ambiguous. Matching files: {matches}")
    return candidates[0]
