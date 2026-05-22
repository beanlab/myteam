from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


DEFAULT_WORKFLOW_CONFIG_FILE = ".config.yaml"
_VALID_USAGE_LOGGING = {"none", "summary", "per_model", "verbose"}


@dataclass(frozen=True)
class DefaultWorkflowConfig:
    agent: str
    model: str
    usage_logging: str
    inactivity_timeout_seconds: int


def load_default_workflow_config(
    local_root: Path,
    *,
    default_agent: str,
    default_model: str,
    default_usage_logging: str,
    default_timeout_seconds: int,
) -> DefaultWorkflowConfig:
    raw_config = {}
    for config_path in _default_workflow_config_paths(local_root):
        if config_path.exists():
            raw_config = _load_yaml_mapping(config_path)
            break
    workflow_config = _workflow_config_mapping(raw_config)

    return DefaultWorkflowConfig(
        agent=_coerce_text(
            workflow_config.get("agent"),
            fallback=default_agent,
        ),
        model=_coerce_text(
            workflow_config.get("model"),
            fallback=default_model,
        ),
        usage_logging=_coerce_usage_logging(
            workflow_config.get("usage_logging"),
            fallback=default_usage_logging,
        ),
        inactivity_timeout_seconds=_coerce_timeout_seconds(
            workflow_config,
            fallback=default_timeout_seconds,
        ),
    )


def _default_workflow_config_paths(local_root: Path) -> list[Path]:
    return [
        local_root / DEFAULT_WORKFLOW_CONFIG_FILE,
        local_root / ".myteam" / DEFAULT_WORKFLOW_CONFIG_FILE,
    ]


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {path}: {exc}") from exc

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain a top-level mapping.")

    return loaded


def _workflow_config_mapping(config: dict[str, Any]) -> dict[str, Any]:
    nested = config.get("default_workflow")
    if isinstance(nested, dict):
        merged = dict(config)
        merged.update(nested)
        return merged
    return config


def _coerce_text(value: Any, *, fallback: str) -> str:
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    return fallback


def _coerce_usage_logging(value: Any, *, fallback: str) -> str:
    if isinstance(value, str):
        text = value.strip().lower()
        if text in _VALID_USAGE_LOGGING:
            return text
    return fallback


def _coerce_timeout_seconds(config: dict[str, Any], *, fallback: int) -> int:
    for key in ("inactivity_timeout_seconds", "timeout_seconds", "timeout"):
        value = config.get(key)
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str):
            try:
                parsed = int(value)
            except ValueError:
                continue
            if parsed > 0:
                return parsed
    return fallback
