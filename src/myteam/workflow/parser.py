from __future__ import annotations

from pathlib import Path

import yaml

from .models import WorkflowDefinition
from .parser_validation import is_identifier_key, validate_step_definition


def load_workflow(path: Path) -> WorkflowDefinition:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("Workflow file must contain a top-level mapping of step names to step definitions.")

    workflow: WorkflowDefinition = {}
    for step_name, definition in loaded.items():
        if not is_identifier_key(step_name):
            raise ValueError(f"Workflow step name must be an identifier: {step_name!r}")
        workflow[step_name] = validate_step_definition(step_name, definition)

    return workflow
