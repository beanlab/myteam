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


def workflow_file(base: Path, workflow: str, prefix: str | Path | None = None) -> Path:
    root = agents_root(base, prefix)
    stem = root / workflow
    matches = [candidate for candidate in (stem.with_suffix(".yaml"), stem.with_suffix(".yml")) if candidate.exists()]

    if not matches:
        raise ValueError(f"Workflow '{workflow}' not found under {root}.")
    if len(matches) > 1:
        raise ValueError(f"Workflow '{workflow}' is ambiguous under {root}; found both .yaml and .yml.")
    return matches[0]
