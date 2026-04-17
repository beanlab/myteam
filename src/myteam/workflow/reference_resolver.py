from __future__ import annotations

from typing import Any

from .models import WorkflowOutput


def resolve_references(value: Any, prior_steps: WorkflowOutput) -> Any:
    raise NotImplementedError("Workflow reference resolution is not implemented yet")
