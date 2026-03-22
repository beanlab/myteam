"""Path helpers and constants for the myteam CLI."""
from __future__ import annotations

from pathlib import Path

APP_NAME = "myteam"
AGENTS_DIRNAME = ".myteam"
BUILTIN_ROOT_NAME = "builtins"
ENCODING = "utf-8"


def base_dir() -> Path:
    """Return the directory from which the CLI was invoked."""
    return Path.cwd()


def agents_root(base: Path) -> Path:
    return base / AGENTS_DIRNAME


def builtin_agents_root() -> Path:
    return Path(__file__).resolve().parent / "builtins"


def role_dir(base: Path, role: str) -> Path:
    return agents_root(base) / role
