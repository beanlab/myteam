from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from ...disclosure import WorkflowStepSettings, split_yaml_frontmatter
from .models import WorkflowDefinition, WorkflowDefinitionModel


def load_workflow(path: Path) -> WorkflowDefinition:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("Workflow file must contain a top-level mapping of step names to step definitions.")

    try:
        workflow = WorkflowDefinitionModel.model_validate(loaded)
    except ValidationError as exc:
        raise ValueError(f"Workflow file at {path} is invalid: {exc}") from exc

    return workflow.model_dump(exclude_none=True)


def load_markdown_workflow(path: Path) -> tuple[str, WorkflowStepSettings | None]:
    text = path.read_text(encoding="utf-8")
    frontmatter, prompt = split_yaml_frontmatter(text)
    if text.startswith("---") and prompt == text:
        raise ValueError(f"Markdown workflow file at {path} has invalid frontmatter.")
    workflow_settings = _workflow_settings_from_frontmatter(frontmatter, path=path)
    return prompt, workflow_settings


def _workflow_settings_from_frontmatter(frontmatter: dict[str, object], *, path: Path) -> WorkflowStepSettings | None:
    workflow_settings = {k: v for k, v in frontmatter.items() if k not in ("name", "description")}
    if not workflow_settings:
        return None

    try:
        return WorkflowStepSettings.model_validate(workflow_settings)
    except ValidationError as exc:
        raise ValueError(f"Markdown workflow file at {path} has invalid workflow settings: {exc}") from exc
