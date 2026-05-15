from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .agents import get_agent_config
from .models import StepDefinition, WorkflowDefinition

_REQUIRED_STEP_KEYS = {"prompt", "output"}
_OPTIONAL_STEP_KEYS = {
    "input",
    "agent",
    "model",
    "extra_args",
    "interactive",
    "session_id",
    "fork",
}
_ALLOWED_STEP_KEYS = _REQUIRED_STEP_KEYS | _OPTIONAL_STEP_KEYS


def _is_identifier_key(value: Any) -> bool:
    return isinstance(value, str) and value.isidentifier()


def _validate_mapping_keys(value: Any, *, context: str) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if not _is_identifier_key(key):
                raise ValueError(f"{context} contains non-identifier key: {key!r}")
            _validate_mapping_keys(nested, context=f"{context}.{key}")
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_mapping_keys(nested, context=f"{context}[{index}]")


def _validate_output_template(value: Any, *, context: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping.")

    for key, nested in value.items():
        if not _is_identifier_key(key):
            raise ValueError(f"{context} contains non-identifier key: {key!r}")
        if isinstance(nested, list):
            raise ValueError(f"{context}.{key} must not contain a list.")
        if isinstance(nested, dict):
            _validate_output_template(nested, context=f"{context}.{key}")


def _validate_step_definition(step_name: str, definition: Any) -> StepDefinition:
    if not isinstance(definition, dict):
        raise ValueError(f"Workflow step '{step_name}' must be a mapping.")

    extra_keys = set(definition) - _ALLOWED_STEP_KEYS
    if extra_keys:
        extras = ", ".join(sorted(str(key) for key in extra_keys))
        raise ValueError(f"Workflow step '{step_name}' has unsupported keys: {extras}.")

    missing_keys = [key for key in ("prompt", "output") if key not in definition]
    if missing_keys:
        missing = ", ".join(missing_keys)
        raise ValueError(f"Workflow step '{step_name}' is missing required keys: {missing}.")

    prompt = definition["prompt"]
    if not isinstance(prompt, str):
        raise ValueError(f"Workflow step '{step_name}' field 'prompt' must be a string.")

    output = definition["output"]
    _validate_output_template(output, context=f"Workflow step '{step_name}'.output")

    validated: StepDefinition = {
        "prompt": prompt,
        "output": output,
        "input": None,
    }

    if "input" in definition:
        _validate_mapping_keys(definition["input"], context=f"Workflow step '{step_name}'.input")
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


def load_workflow(path: Path) -> WorkflowDefinition:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("Workflow file must contain a top-level mapping of step names to step definitions.")

    workflow: WorkflowDefinition = {}
    for step_name, definition in loaded.items():
        if not _is_identifier_key(step_name):
            raise ValueError(f"Workflow step name must be an identifier: {step_name!r}")
        workflow[step_name] = _validate_step_definition(step_name, definition)

    return workflow
