from __future__ import annotations

from pathlib import Path
from typing import Any

from ..agents import get_agent_config
from ..definition.models import ProjectWorkflowDefaults, StepDefinition

_ALLOWED_KEYS = {
    "agent",
    "model",
    "interactive",
    "session_id",
    "fork",
    "extra_args",
    "usage_logging",
    "timeout",
}
_REQUIRED_STEP_KEYS = {"prompt"}
_OPTIONAL_STEP_KEYS = {
    "output",
    "input",
    "agent",
    "model",
    "extra_args",
    "interactive",
    "session_id",
    "fork",
}
_ALLOWED_STEP_KEYS = _REQUIRED_STEP_KEYS | _OPTIONAL_STEP_KEYS


def validate_step_execution_args(
    *,
    agent_name: str,
    interactive: bool,
    session_id: str | None,
    fork: bool,
    extra_args: list[str] | None,
    model: str | None,
) -> None:
    if not agent_name or not isinstance(agent_name, str):
        raise ValueError("Step definition is missing required string 'agent'.")
    if not isinstance(interactive, bool):
        raise ValueError("Step field 'interactive' must be a boolean when provided.")
    if not isinstance(fork, bool):
        raise ValueError("Step field 'fork' must be a boolean when provided.")
    if session_id is not None and (not isinstance(session_id, str) or not session_id):
        raise ValueError("Step field 'session_id' must be a non-empty string when provided.")
    if fork and session_id is None:
        raise ValueError("Step field 'session_id' is required when 'fork' is true.")
    if extra_args is not None:
        if not isinstance(extra_args, list):
            raise ValueError("Step field 'extra_args' must be a list of strings when provided.")
        for index, arg in enumerate(extra_args):
            if not isinstance(arg, str):
                raise ValueError(f"Step field 'extra_args[{index}]' must be a string.")
    if model is not None and (not isinstance(model, str) or not model):
        raise ValueError("Step field 'model' must be a non-empty string when provided.")


def validate_step_output(output_template: dict[str, Any], output_value: Any) -> None:
    _validate_output_node(output_template, output_value, path="output")


def _validate_output_node(template: Any, value: Any, *, path: str) -> None:
    if not isinstance(template, dict):
        return
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be a mapping.")
    for key, nested in template.items():
        if key not in value:
            raise ValueError(f"{path}.{key} is missing.")
        _validate_output_node(nested, value[key], path=f"{path}.{key}")


def is_identifier_key(value: Any) -> bool:
    return isinstance(value, str) and value.isidentifier()


def validate_mapping_keys(value: Any, *, context: str) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if not is_identifier_key(key):
                raise ValueError(f"{context} contains non-identifier key: {key!r}")
            validate_mapping_keys(nested, context=f"{context}.{key}")
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            validate_mapping_keys(nested, context=f"{context}[{index}]")


def validate_output_template(value: Any, *, context: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping.")

    for key, nested in value.items():
        if not is_identifier_key(key):
            raise ValueError(f"{context} contains non-identifier key: {key!r}")
        if isinstance(nested, list):
            raise ValueError(f"{context}.{key} must not contain a list.")
        if isinstance(nested, dict):
            validate_output_template(nested, context=f"{context}.{key}")


def validate_step_definition(step_name: str, definition: Any) -> StepDefinition:
    if not isinstance(definition, dict):
        raise ValueError(f"Workflow step '{step_name}' must be a mapping.")

    extra_keys = set(definition) - _ALLOWED_STEP_KEYS
    if extra_keys:
        extras = ", ".join(sorted(str(key) for key in extra_keys))
        raise ValueError(f"Workflow step '{step_name}' has unsupported keys: {extras}.")

    missing_keys = [key for key in ("prompt",) if key not in definition]
    if missing_keys:
        missing = ", ".join(missing_keys)
        raise ValueError(f"Workflow step '{step_name}' is missing required keys: {missing}.")

    prompt = definition["prompt"]
    if not isinstance(prompt, str):
        raise ValueError(f"Workflow step '{step_name}' field 'prompt' must be a string.")

    output = definition.get("output", {})
    validate_output_template(output, context=f"Workflow step '{step_name}'.output")

    validated: StepDefinition = {
        "prompt": prompt,
        "input": None,
        "output": output,
    }

    if "input" in definition:
        validate_mapping_keys(definition["input"], context=f"Workflow step '{step_name}'.input")
        validated["input"] = definition["input"]

    if "agent" in definition:
        agent = definition["agent"]
        if not isinstance(agent, str):
            raise ValueError(f"Workflow step '{step_name}' field 'agent' must be a string.")
        try:
            get_agent_config(agent)
        except KeyError as exc:
            raise ValueError(str(exc)) from exc
        validated["agent"] = agent

    if "model" in definition:
        model = definition["model"]
        if not isinstance(model, str) or not model:
            raise ValueError(f"Workflow step '{step_name}' field 'model' must be a non-empty string.")
        validated["model"] = model

    if "extra_args" in definition:
        extra_args = definition["extra_args"]
        if not isinstance(extra_args, list):
            raise ValueError(f"Workflow step '{step_name}' field 'extra_args' must be a list of strings.")
        for index, arg in enumerate(extra_args):
            if not isinstance(arg, str):
                raise ValueError(f"Workflow step '{step_name}' field 'extra_args[{index}]' must be a string.")
        validated["extra_args"] = extra_args

    if "interactive" in definition:
        interactive = definition["interactive"]
        if not isinstance(interactive, bool):
            raise ValueError(f"Workflow step '{step_name}' field 'interactive' must be a boolean.")
        validated["interactive"] = interactive

    if "session_id" in definition:
        session_id = definition["session_id"]
        if not isinstance(session_id, str) or not session_id:
            raise ValueError(f"Workflow step '{step_name}' field 'session_id' must be a non-empty string.")
        validated["session_id"] = session_id

    if "fork" in definition:
        fork = definition["fork"]
        if not isinstance(fork, bool):
            raise ValueError(f"Workflow step '{step_name}' field 'fork' must be a boolean.")
        if fork and "session_id" not in definition:
            raise ValueError(f"Workflow step '{step_name}' field 'session_id' is required when 'fork' is true.")
        validated["fork"] = fork

    return validated


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
        timeout=_load_optional_positive_int(
            defaults,
            "timeout",
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
