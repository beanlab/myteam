from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, ValidationError, field_validator

MYTEAM_CONFIG_FILENAME = ".myteam.yaml"
# Legacy filename retained for compatibility with code/tests that still call
# load_workflow_defaults(myteam_folder) during the workflow refactor.
CONFIG_FILENAME = ".config.yaml"


class WorkflowDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    agent: Optional[str] = Field(default=None, min_length=1)
    model: Optional[str] = Field(default=None, min_length=1)
    reasoning: Optional[str] = Field(default=None, min_length=1)
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
            return tuple(str(item) for item in value)
        return value


@dataclass(frozen=True)
class MyteamConfig:
    defaults: WorkflowDefaults = field(default_factory=WorkflowDefaults)
    agents: dict[str, str] = field(default_factory=dict)
    path: Path | None = None


def load_myteam_config(cwd: Path | None = None) -> MyteamConfig | None:
    """Load `.myteam.yaml` from the working directory, if present."""

    root = Path.cwd() if cwd is None else cwd
    config_path = root / MYTEAM_CONFIG_FILENAME if root.is_dir() else root
    if not config_path.exists():
        return None

    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse myteam config at {config_path}: {exc}") from exc

    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Myteam config at {config_path} must be a YAML mapping.")

    defaults_raw = loaded.get("defaults") or {}
    if not isinstance(defaults_raw, dict):
        raise ValueError(f"Myteam config defaults at {config_path} must be a mapping.")

    agents_raw = loaded.get("agents") or {}
    if not isinstance(agents_raw, dict):
        raise ValueError(f"Myteam config agents at {config_path} must be a mapping.")

    try:
        defaults = WorkflowDefaults.model_validate(defaults_raw)
    except ValidationError as exc:
        raise ValueError(f"Myteam config defaults at {config_path} are invalid: {exc}") from exc

    agents: dict[str, str] = {}
    for name, target in agents_raw.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Myteam config agents at {config_path} must use non-empty string names.")
        if not isinstance(target, str) or not target.strip():
            raise ValueError(f"Myteam config agent '{name}' at {config_path} must be a non-empty string target.")
        agents[name] = target

    return MyteamConfig(defaults=defaults, agents=agents, path=config_path)


def load_workflow_defaults(myteam_folder: Path) -> WorkflowDefaults | None:
    """Load workflow defaults from legacy config or the new `.myteam.yaml`.

    New code should use load_myteam_config(). This helper remains so existing
    imports continue to work during the workflow runtime refactor.
    """

    new_config = load_myteam_config(myteam_folder)
    if new_config is not None:
        return new_config.defaults

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
