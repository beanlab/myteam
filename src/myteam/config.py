from __future__ import annotations

import warnings
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
MYTEAM_CONFIG_PATH = (".myteam", "config.yaml")
class MyteamConfigDeprecationWarning(UserWarning):
    """Warning emitted when the deprecated `.myteam.yaml` is present."""


def _select_config_path(root: Path) -> Path | None:
    preferred_path = root.joinpath(*MYTEAM_CONFIG_PATH)
    deprecated_path = root / MYTEAM_CONFIG_FILENAME

    if deprecated_path.exists():
        warnings.warn(
            f"{deprecated_path} is deprecated; use {preferred_path} instead.",
            MyteamConfigDeprecationWarning,
            stacklevel=3,
        )

    if preferred_path.exists():
        return preferred_path
    if deprecated_path.exists():
        return deprecated_path
    return None


def normalize_session_name(value: Any) -> str | None:
    if value is None:
        return None
    name = str(value)
    if "\n" in name or "\r" in name:
        raise ValueError("Session name must not contain newline characters.")
    return name


class AgentSettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    agent: Optional[str] = Field(default=None, min_length=1)
    session_name: Optional[str] = None
    model: Optional[str] = Field(default=None, min_length=1)
    reasoning: Optional[str] = Field(default=None, min_length=1)
    interactive: Optional[bool] = None
    session_id: Optional[str] = Field(default=None, min_length=1)
    system_prompt: Optional[bool] = None
    fork: Optional[bool] = Field(default=None)
    extra_args: Optional[tuple[str, ...]] = Field(default=None)

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


AGENT_SETTING_FIELDS = tuple(AgentSettingsModel.model_fields)


class WorkflowDefaults(AgentSettingsModel):
    usage_logging: Optional[Literal["none", "summary", "per_model", "verbose"]] = Field(default=None)
    timeout: Optional[PositiveInt] = Field(default=None)


@dataclass(frozen=True)
class MyteamConfig:
    defaults: WorkflowDefaults = field(default_factory=WorkflowDefaults)
    agents: dict[str, str] = field(default_factory=dict)
    jinja_functions: dict[str, str] = field(default_factory=dict)
    _agent_origins: dict[str, Path] = field(default_factory=dict, repr=False, compare=False)
    _jinja_function_origins: dict[str, Path] = field(default_factory=dict, repr=False, compare=False)


@dataclass(frozen=True)
class _ConfigSource:
    path: Path
    defaults: WorkflowDefaults
    agents: dict[str, str]
    jinja_functions: dict[str, str]


def load_myteam_config(cwd: Path | None = None) -> MyteamConfig | None:
    """Load and merge the selected global and project configuration files."""

    root = Path.cwd() if cwd is None else Path(cwd)
    project_root = root if root.is_dir() else root.parent
    paths = [
        path
        for path in (_select_config_path(Path.home()), _select_config_path(project_root))
        if path is not None
    ]
    unique_paths: list[Path] = []
    for path in paths:
        if not any(path.samefile(existing) for existing in unique_paths):
            unique_paths.append(path)

    if not unique_paths:
        return None

    return _merge_sources([_load_source(path) for path in unique_paths])


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

    jinja_functions_value = loaded.get("jinja_functions")
    jinja_functions_raw = {} if jinja_functions_value is None else jinja_functions_value
    if not isinstance(jinja_functions_raw, dict):
        raise ValueError(f"Myteam config jinja_functions at {config_path} must be a mapping.")

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

    jinja_functions: dict[str, str] = {}
    for name, target in jinja_functions_raw.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Myteam config jinja_functions at {config_path} must use non-empty string names.")
        if not isinstance(target, str) or not _is_python_symbol_target(target):
            raise ValueError(
                f"Myteam config Jinja function '{name}' at {config_path} "
                "must use a non-empty 'file.py::function_name' target."
            )
        jinja_functions[name] = target

    return _ConfigSource(
        path=config_path,
        defaults=defaults,
        agents=agents,
        jinja_functions=jinja_functions,
    )


def _is_python_symbol_target(target: str) -> bool:
    path, separator, symbol = target.partition("::")
    return bool(
        separator
        and path.strip()
        and Path(path.strip()).suffix == ".py"
        and symbol.strip()
        and "::" not in symbol
    )


def _merge_sources(sources: list[_ConfigSource]) -> MyteamConfig:
    default_values: dict[str, Any] = {}
    agents: dict[str, str] = {}
    jinja_functions: dict[str, str] = {}
    agent_origins: dict[str, Path] = {}
    jinja_function_origins: dict[str, Path] = {}

    for source in sources:
        default_values.update(source.defaults.model_dump(exclude_unset=True))
        agents.update(source.agents)
        jinja_functions.update(source.jinja_functions)
        agent_origins.update(dict.fromkeys(source.agents, source.path.parent))
        jinja_function_origins.update(dict.fromkeys(source.jinja_functions, source.path.parent))

    return MyteamConfig(
        defaults=WorkflowDefaults.model_validate(default_values),
        agents=agents,
        jinja_functions=jinja_functions,
        _agent_origins=agent_origins,
        _jinja_function_origins=jinja_function_origins,
    )
