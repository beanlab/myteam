"""Task runtime package."""

from __future__ import annotations

from pathlib import Path

from ..disclosure import _collect_skill_names, _collect_task_names, get_active_myteam_root
from ..paths import DEFAULT_LOCAL_ROOT, base_dir
from .definition.parser import load_markdown_task, load_task
from .definition.models import StepResult
from .execution.engine import run_task
from .execution.steps import AgentContext, run_agent

__all__ = [
    "AgentContext",
    "list_skills",
    "list_tasks",
    "run_agent",
    "load_markdown_task",
    "load_task",
    "run_task",
    "StepResult",
]


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
