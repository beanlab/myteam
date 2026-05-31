from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from ...disclosure import TaskStepSettings, split_yaml_frontmatter
from .models import TaskDefinition, TaskDefinitionModel


def load_task(path: Path) -> TaskDefinition:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("Task file must contain a top-level mapping with a 'steps' section.")

    steps = loaded.get("steps")
    if steps is None:
        steps = {}
    if not isinstance(steps, dict):
        raise ValueError("Task file 'steps' section must be a mapping of step names to step definitions.")

    try:
        task_definition = TaskDefinitionModel.model_validate(steps)
    except ValidationError as exc:
        raise ValueError(f"Task file at {path} is invalid: {exc}") from exc

    return task_definition.model_dump(exclude_none=True)


def load_markdown_task(path: Path) -> tuple[str, TaskStepSettings | None]:
    text = path.read_text(encoding="utf-8")
    frontmatter, prompt = split_yaml_frontmatter(text)
    if text.startswith("---") and prompt == text:
        raise ValueError(f"Markdown task file at {path} has invalid frontmatter.")
    task_settings = _task_settings_from_frontmatter(frontmatter, path=path)
    return prompt, task_settings


def _task_settings_from_frontmatter(frontmatter: dict[str, object], *, path: Path) -> TaskStepSettings | None:
    task_settings = {k: v for k, v in frontmatter.items() if k not in ("name", "description")}
    if not task_settings:
        return None

    try:
        return TaskStepSettings.model_validate(task_settings)
    except ValidationError as exc:
        raise ValueError(f"Markdown task file at {path} has invalid task settings: {exc}") from exc
