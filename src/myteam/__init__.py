"""Myteam package for managing agent role directories."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import tomllib

__all__ = ["__version__"]


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
