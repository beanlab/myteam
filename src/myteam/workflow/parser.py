from __future__ import annotations

from pathlib import Path

from .models import WorkflowDefinition


def load_workflow(path: Path) -> WorkflowDefinition:
    raise NotImplementedError(f"Workflow parsing is not implemented yet for {path}")
