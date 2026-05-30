"""Myteam package for managing agent role directories."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import tomllib

from .disclosure import _collect_skill_names, _collect_task_names, get_active_myteam_root
from .paths import DEFAULT_LOCAL_ROOT, base_dir

__all__ = ["__version__", "list_skills", "list_tasks"]


def _resolve_listing_root(directory: str | Path | None) -> tuple[Path, Path]:
    cwd = base_dir()
    root = get_active_myteam_root(cwd)
    if root == cwd and (cwd / DEFAULT_LOCAL_ROOT).is_dir():
        root = cwd / DEFAULT_LOCAL_ROOT
    if directory is None:
        return root, root

    folder = Path(directory)
    if not folder.is_absolute():
        folder = root / folder
    return folder, root


def list_tasks(directory: str | Path | None = None) -> list[str]:
    folder, root = _resolve_listing_root(directory)
    return _collect_task_names(folder, root, [])


def list_skills(directory: str | Path | None = None) -> list[str]:
    folder, root = _resolve_listing_root(directory)
    return _collect_skill_names(folder, root, [])


def _project_version() -> str:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if pyproject.exists():
        with pyproject.open("rb") as handle:
            project = tomllib.load(handle)["project"]
        return str(project["version"])

    try:
        return version("myteam")
    except PackageNotFoundError:
        raise RuntimeError("Unable to determine myteam version") from None


__version__ = _project_version()
