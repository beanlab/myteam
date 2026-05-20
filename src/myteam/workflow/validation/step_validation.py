from __future__ import annotations

from typing import Any


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
