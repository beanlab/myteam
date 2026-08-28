from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    ValidationError,
    field_validator,
)

MYTEAM_CONFIG_FILENAME = ".myteam.yaml"
# Legacy filename retained for compatibility with code/tests that still call
# load_workflow_defaults(myteam_folder) during the workflow refactor.
CONFIG_FILENAME = ".config.yaml"


def normalize_session_name(value: Any) -> str | None:
    if value is None:
        return None
    name = str(value)
    if "\n" in name or "\r" in name:
        raise ValueError("Session name must not contain newline characters.")
    return name


class WorkflowDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    agent: Optional[str] = Field(default=None, min_length=1)
    session_name: Optional[str] = None
    model: Optional[str] = Field(default=None, min_length=1)
    reasoning: Optional[str] = Field(default=None, min_length=1)
    interactive: Optional[bool] = None
    session_id: Optional[str] = Field(default=None, min_length=1)
    fork: Optional[bool] = Field(default=None)
    extra_args: Optional[tuple[str, ...]] = Field(default=None)
    usage_logging: Optional[Literal["none", "summary", "per_model", "verbose"]] = Field(default=None)
    timeout: Optional[PositiveInt] = Field(default=None)

    @field_validator("session_name", mode="before")
    @classmethod
    def _normalize_session_name(cls, value: Any) -> str | None:
        return normalize_session_name(value)

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
    _agent_origins: dict[str, Path] = field(default_factory=dict, repr=False, compare=False)


@dataclass(frozen=True)
class _ConfigSource:
    path: Path
    defaults: WorkflowDefaults
    agents: dict[str, str]


def load_myteam_config(cwd: Path | None = None) -> MyteamConfig | None:
    """Load and merge the home and working-directory `.myteam.yaml` files."""

    global_path = Path.home() / MYTEAM_CONFIG_FILENAME
    root = Path.cwd() if cwd is None else Path(cwd)
    project_path = root / MYTEAM_CONFIG_FILENAME if root.is_dir() else root

    paths = [path for path in (global_path, project_path) if path.exists()]
    if not paths:
        return None
    if len(paths) == 2 and paths[0].samefile(paths[1]):
        paths.pop()

    return _merge_sources([_load_source(path) for path in paths])


def _load_source(config_path: Path) -> _ConfigSource:
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

    return _ConfigSource(path=config_path, defaults=defaults, agents=agents)


def _merge_sources(sources: list[_ConfigSource]) -> MyteamConfig:
    default_values: dict[str, Any] = {}
    agents: dict[str, str] = {}
    agent_origins: dict[str, Path] = {}

    for source in sources:
        default_values.update(source.defaults.model_dump(exclude_unset=True))
        agents.update(source.agents)
        agent_origins.update(dict.fromkeys(source.agents, source.path.parent))

    return MyteamConfig(
        defaults=WorkflowDefaults.model_validate(default_values),
        agents=agents,
        _agent_origins=agent_origins,
    )


def load_workflow_defaults(myteam_folder: Path) -> WorkflowDefaults | None:
    """Load workflow defaults from legacy config or the effective `.myteam.yaml`."""

    project_root = myteam_folder.parent if myteam_folder.name == ".myteam" else myteam_folder
    project_path = project_root / MYTEAM_CONFIG_FILENAME
    new_config = load_myteam_config(project_root)

    config_path = myteam_folder / CONFIG_FILENAME
    if not project_path.exists() and config_path.exists():
        return _load_legacy_defaults(config_path)
    if new_config is not None:
        return new_config.defaults
    if not config_path.exists():
        return None
    return _load_legacy_defaults(config_path)


def _load_legacy_defaults(config_path: Path) -> WorkflowDefaults:
    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse workflow project config at {config_path}: {exc}") from exc

    try:
        return WorkflowDefaults.model_validate(loaded)
    except ValidationError as exc:
        raise ValueError(f"Workflow project config at {config_path} is invalid: {exc}") from exc
