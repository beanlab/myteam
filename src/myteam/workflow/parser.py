from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

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
