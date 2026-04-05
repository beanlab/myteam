"""Workflow definition parsing, input resolution, and output validation."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .paths import AGENTS_DIRNAME, ENCODING


class WorkflowError(RuntimeError):
    """Raised when a workflow cannot be loaded or executed."""


@dataclass(frozen=True)
class WorkflowStep:
    id: str
    role: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]


@dataclass(frozen=True)
class WorkflowDefinition:
    path: Path
    steps: list[WorkflowStep]


def load_workflow_definition(path: Path) -> WorkflowDefinition:
    try:
        loaded = yaml.safe_load(path.read_text(encoding=ENCODING))
    except OSError as exc:
        raise WorkflowError(f"failed to read workflow file {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise WorkflowError(f"failed to parse workflow YAML {path}: {exc}") from exc

    if not isinstance(loaded, dict) or not loaded:
        raise WorkflowError("workflow file must be a non-empty YAML mapping")

    steps: list[WorkflowStep] = []
    seen_steps: set[str] = set()
    for step_id, raw_step in loaded.items():
        if not isinstance(step_id, str) or not step_id:
            raise WorkflowError("workflow step names must be non-empty strings")
        if step_id in seen_steps:
            raise WorkflowError(f"duplicate workflow step '{step_id}'")
        if not isinstance(raw_step, dict):
            raise WorkflowError(f"workflow step '{step_id}' must be a mapping")
        role = raw_step.get("role")
        if not isinstance(role, str) or not role.strip():
            raise WorkflowError(f"workflow step '{step_id}' is missing a role")
        inputs = raw_step.get("inputs", {})
        outputs = raw_step.get("outputs")
        if inputs is None:
            inputs = {}
        if not isinstance(inputs, dict):
            raise WorkflowError(f"workflow step '{step_id}' inputs must be a mapping")
        if not isinstance(outputs, dict) or not outputs:
            raise WorkflowError(f"workflow step '{step_id}' outputs must be a non-empty mapping")
        _validate_output_names(step_id, outputs)
        _validate_input_references(step_id, inputs, seen_steps)
        steps.append(
            WorkflowStep(
                id=step_id,
                role=_normalize_role_path(role),
                inputs=inputs,
                outputs=outputs,
            )
        )
        seen_steps.add(step_id)

    return WorkflowDefinition(path=path, steps=steps)


def resolve_inputs(inputs: dict[str, Any], completed_outputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        key: _resolve_input_value(value, completed_outputs)
        for key, value in inputs.items()
    }


def parse_step_output(message: str, outputs: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = json.loads(message)
    except json.JSONDecodeError as exc:
        stripped = _strip_json_fence(message)
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            raise WorkflowError(f"workflow step returned invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise WorkflowError("workflow step output must be a JSON object")
    expected_keys = set(outputs)
    actual_keys = set(parsed)
    if actual_keys != expected_keys:
        raise WorkflowError(
            f"workflow step output keys {sorted(actual_keys)} do not match required outputs {sorted(expected_keys)}"
        )
    return parsed


def build_output_schema(outputs: dict[str, Any]) -> dict[str, Any]:
    properties = {
        name: _build_output_property_schema(description)
        for name, description in outputs.items()
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(outputs.keys()),
        "additionalProperties": False,
    }


def _resolve_input_value(value: Any, completed_outputs: dict[str, dict[str, Any]]) -> Any:
    if isinstance(value, dict):
        if set(value) == {"from"} and isinstance(value["from"], str):
            return _resolve_output_reference(value["from"], completed_outputs)
        return {
            key: _resolve_input_value(nested_value, completed_outputs)
            for key, nested_value in value.items()
        }
    if isinstance(value, list):
        return [_resolve_input_value(item, completed_outputs) for item in value]
    return value


def _resolve_output_reference(reference: str, completed_outputs: dict[str, dict[str, Any]]) -> Any:
    step_id, separator, output_name = reference.partition(".")
    if not separator or not output_name:
        raise WorkflowError(f"invalid workflow output reference '{reference}'")
    if step_id not in completed_outputs:
        raise WorkflowError(f"workflow output reference '{reference}' is not available yet")
    step_output = completed_outputs[step_id]
    if output_name not in step_output:
        raise WorkflowError(f"workflow output reference '{reference}' does not exist")
    return step_output[output_name]


def _validate_output_names(step_id: str, outputs: dict[str, Any]) -> None:
    seen_outputs: set[str] = set()
    for output_name in outputs:
        if not isinstance(output_name, str) or not output_name:
            raise WorkflowError(f"workflow step '{step_id}' has an invalid output name")
        if output_name in seen_outputs:
            raise WorkflowError(f"workflow step '{step_id}' has duplicate output '{output_name}'")
        seen_outputs.add(output_name)


def _validate_input_references(step_id: str, value: Any, seen_steps: set[str]) -> None:
    if isinstance(value, dict):
        if set(value) == {"from"} and isinstance(value["from"], str):
            ref_step_id, separator, _ = value["from"].partition(".")
            if not separator or ref_step_id not in seen_steps:
                raise WorkflowError(
                    f"workflow step '{step_id}' references unavailable output '{value['from']}'"
                )
            return
        for nested_value in value.values():
            _validate_input_references(step_id, nested_value, seen_steps)
    elif isinstance(value, list):
        for item in value:
            _validate_input_references(step_id, item, seen_steps)


def _normalize_role_path(role: str) -> str:
    normalized = role.strip()
    if normalized == AGENTS_DIRNAME:
        return ""
    if normalized.startswith(f"{AGENTS_DIRNAME}/"):
        return normalized.removeprefix(f"{AGENTS_DIRNAME}/")
    if normalized.startswith(f"./{AGENTS_DIRNAME}/"):
        return normalized.removeprefix(f"./{AGENTS_DIRNAME}/")
    return normalized


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text
    lines = stripped.splitlines()
    if len(lines) < 3:
        return text
    return "\n".join(lines[1:-1])


def _build_output_property_schema(output_spec: Any) -> dict[str, Any]:
    # Keep the simple template.yaml shape ergonomic: a scalar output declaration
    # means "this key is a string result with this description".
    if isinstance(output_spec, dict):
        schema = dict(output_spec)
        schema_type = schema.get("type")
        if not isinstance(schema_type, str) or not schema_type:
            raise WorkflowError("workflow output schema mappings must include a non-empty 'type'")
        return schema

    return {
        "type": "string",
        "description": str(output_spec),
    }
