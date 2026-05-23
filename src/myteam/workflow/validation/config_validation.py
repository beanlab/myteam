from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import ProjectWorkflowDefaults


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
            f"Workflow project config at {config_path} must define workflow defaults under 'workflow_agent_defaults'."
        )

    unknown_keys = sorted(set(defaults) - _ALLOWED_KEYS)
    if unknown_keys:
        joined = ", ".join(unknown_keys)
        raise ValueError(f"Workflow project config at {config_path} contains unknown keys: {joined}")

    return ProjectWorkflowDefaults(
        agent=_load_optional_string(defaults, "agent", config_path),
        model=_load_optional_string(defaults, "model", config_path),
        interactive=_load_optional_bool(defaults, "interactive", config_path),
        session_id=_load_optional_string(defaults, "session_id", config_path),
        fork=_load_optional_bool(defaults, "fork", config_path),
        extra_args=_load_optional_string_list(defaults, "extra_args", config_path),
        usage_logging=_load_optional_usage_logging(defaults, config_path),
        inactivity_timeout_seconds=_load_optional_positive_int(
            defaults,
            "inactivity_timeout_seconds",
            config_path,
        ),
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
