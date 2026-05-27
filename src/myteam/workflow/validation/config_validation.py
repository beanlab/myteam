from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..models import ProjectWorkflowDefaults


def validate_project_workflow_defaults(
    loaded: Any,
    *,
    config_path: Path,
) -> ProjectWorkflowDefaults:
    if loaded is None:
        return ProjectWorkflowDefaults()
    if not isinstance(loaded, dict):
        raise ValueError(f"Workflow project config at {config_path} must be a mapping.")

    defaults = loaded.get("workflow_agent_defaults")
    if not isinstance(defaults, dict):
        raise ValueError(
            f"Workflow project config at {config_path} must define workflow defaults under "
            "'workflow_agent_defaults'."
        )

    try:
        return ProjectWorkflowDefaults.model_validate(defaults)
    except ValidationError as exc:
        raise ValueError(f"Workflow project config at {config_path} is invalid: {exc}") from exc
