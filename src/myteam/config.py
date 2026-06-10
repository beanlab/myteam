from __future__ import annotations

from pathlib import Path
from typing import Optional, Literal, Any

import yaml
from pydantic import ValidationError, BaseModel, ConfigDict, Field, PositiveInt, field_validator

CONFIG_FILENAME = ".config.yaml"


class WorkflowDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    agent: Optional[str] = Field(default=None, min_length=1)
    model: Optional[str] = Field(default=None, min_length=1)
    interactive: Optional[bool] = None
    session_id: Optional[str] = Field(default=None, min_length=1)
    fork: Optional[bool] = Field(default=None)
    extra_args: Optional[tuple[str, ...]] = Field(default=None)
    usage_logging: Optional[Literal["none", "summary", "per_model", "verbose"]] = Field(default=None)
    timeout: Optional[PositiveInt] = Field(default=None)

    @field_validator("extra_args", mode="before")
    @classmethod
    def _coerce_extra_args(cls, value: Any) -> tuple[str, ...] | None:
        if value is None:
            return None
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(value)
        return value


def load_workflow_defaults(myteam_folder: Path) -> WorkflowDefaults | None:
    config_path = myteam_folder / CONFIG_FILENAME
    if not config_path.exists():
        return None

    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse workflow project config at {config_path}: {exc}") from exc

    try:
        return WorkflowDefaults.model_validate(loaded)
    except ValidationError as exc:
        raise ValueError(f"Workflow project config at {config_path} is invalid: {exc}") from exc

