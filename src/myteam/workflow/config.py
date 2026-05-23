from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


CONFIG_FILENAME = ".config.yaml"
CONFIG_DIRNAME = ".myteam"
_ALLOWED_KEYS = {
    "agent",
    "model",
    "interactive",
    "session_id",
    "fork",
    "extra_args",
    "usage_logging",
    "inactivity_timeout_seconds",
}


@dataclass(frozen=True)
class ProjectWorkflowDefaults:
    agent: str | None = None
    model: str | None = None
    interactive: bool | None = None
    session_id: str | None = None
    fork: bool | None = None
    extra_args: tuple[str, ...] | None = None
    usage_logging: str | None = None
    inactivity_timeout_seconds: int | None = None


def load_project_workflow_defaults(project_root: Path) -> ProjectWorkflowDefaults | None:
    config_path = project_root / CONFIG_DIRNAME / CONFIG_FILENAME
    if not config_path.exists():
        return None

    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse workflow project config at {config_path}: {exc}") from exc

    if loaded is None:
        return ProjectWorkflowDefaults()
    if not isinstance(loaded, dict):
        raise ValueError(f"Workflow project config at {config_path} must be a mapping.")

    if "workflow_agent_defaults" in loaded:
        unknown_keys = sorted(set(loaded) - {"workflow_agent_defaults"})
        if unknown_keys:
            joined = ", ".join(unknown_keys)
            raise ValueError(f"Workflow project config at {config_path} contains unknown keys: {joined}")
        loaded = loaded["workflow_agent_defaults"]
        if loaded is None:
            return ProjectWorkflowDefaults()
        if not isinstance(loaded, dict):
            raise ValueError(
                f"Workflow project config at {config_path} field 'workflow_agent_defaults' must be a mapping."
            )

    unknown_keys = sorted(set(loaded) - _ALLOWED_KEYS)
    if unknown_keys:
        joined = ", ".join(unknown_keys)
        raise ValueError(f"Workflow project config at {config_path} contains unknown keys: {joined}")

    return ProjectWorkflowDefaults(
        agent=_load_optional_string(loaded, "agent", config_path),
        model=_load_optional_string(loaded, "model", config_path),
        interactive=_load_optional_bool(loaded, "interactive", config_path),
        session_id=_load_optional_string(loaded, "session_id", config_path),
        fork=_load_optional_bool(loaded, "fork", config_path),
        extra_args=_load_optional_string_list(loaded, "extra_args", config_path),
        usage_logging=_load_optional_usage_logging(loaded, config_path),
        inactivity_timeout_seconds=_load_optional_positive_int(loaded, "inactivity_timeout_seconds", config_path),
    )


def _load_optional_string(loaded: dict[str, Any], key: str, config_path: Path) -> str | None:
    value = loaded.get(key)
    if value is None:
        return None
    if isinstance(value, str) and value:
        return value
    raise ValueError(f"Workflow project config at {config_path} field '{key}' must be a non-empty string.")


def _load_optional_bool(loaded: dict[str, Any], key: str, config_path: Path) -> bool | None:
    value = loaded.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise ValueError(f"Workflow project config at {config_path} field '{key}' must be a boolean.")


def _load_optional_string_list(
    loaded: dict[str, Any],
    key: str,
    config_path: Path,
) -> tuple[str, ...] | None:
    value = loaded.get(key)
    if value is None:
        return None
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(value)
    raise ValueError(f"Workflow project config at {config_path} field '{key}' must be a list of strings.")


def _load_optional_usage_logging(loaded: dict[str, Any], config_path: Path) -> str | None:
    value = loaded.get("usage_logging")
    if value is None:
        return None
    if value in {"none", "summary", "per_model", "verbose"}:
        return value
    raise ValueError(
        f"Workflow project config at {config_path} field 'usage_logging' must be one of: "
        "none, summary, per_model, verbose."
    )


def _load_optional_positive_int(loaded: dict[str, Any], key: str, config_path: Path) -> int | None:
    value = loaded.get(key)
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    raise ValueError(f"Workflow project config at {config_path} field '{key}' must be a positive integer.")
