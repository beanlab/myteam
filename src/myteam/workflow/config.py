from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import ProjectWorkflowDefaults


CONFIG_FILENAME = ".config.yaml"
CONFIG_DIRNAME = ".myteam"


def load_project_workflow_defaults(project_root: Path) -> ProjectWorkflowDefaults | None:
    config_path = project_root / CONFIG_DIRNAME / CONFIG_FILENAME
    if not config_path.exists():
        return None

    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse workflow project config at {config_path}: {exc}") from exc

    try:
        return ProjectWorkflowDefaults.model_validate(loaded)
    except ValidationError as exc:
        raise ValueError(f"Workflow project config at {config_path} is invalid: {exc}") from exc
