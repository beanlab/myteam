from __future__ import annotations

from typing import Any

from .models import WorkflowOutput


def _resolve_reference_path(reference: str, prior_steps: WorkflowOutput) -> Any:
    if not reference.startswith("$") or reference.startswith("$$"):
        raise ValueError(f"Invalid workflow reference: {reference!r}")

    path = reference[1:]
    if not path:
        raise ValueError("Workflow reference cannot be empty.")

    tokens = path.split(".")
    if any(not token for token in tokens):
        raise ValueError(f"Workflow reference has an empty path segment: {reference!r}")

    step_name = tokens[0]
    if step_name not in prior_steps:
        raise ValueError(f"Workflow reference points to unknown step: {step_name}")

    current: Any = prior_steps[step_name]
    for token in tokens[1:]:
        if isinstance(current, list):
            raise ValueError(f"Workflow references do not support list traversal: {reference!r}")
        if not isinstance(current, dict):
            raise ValueError(f"Workflow reference cannot traverse into non-mapping value: {reference!r}")
        if token not in current:
            raise ValueError(f"Workflow reference path not found: {reference!r}")
        current = current[token]

    return current


def resolve_references(value: Any, prior_steps: WorkflowOutput) -> Any:
    if isinstance(value, str):
        if value.startswith("$$"):
            return value[1:]
        if value.startswith("$"):
            return _resolve_reference_path(value, prior_steps)
        return value

    if isinstance(value, list):
        return [resolve_references(item, prior_steps) for item in value]

    if isinstance(value, dict):
        return {
            key: resolve_references(nested_value, prior_steps)
            for key, nested_value in value.items()
        }

    return value
