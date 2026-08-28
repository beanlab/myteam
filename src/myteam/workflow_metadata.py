from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Literal

from .frontmatter import parse_python_frontmatter, split_markdown_frontmatter

WorkflowFormat = Literal["python", "markdown"]


@dataclasses.dataclass(frozen=True)
class WorkflowMetadata:
    format: WorkflowFormat
    usage: str | None = None
    input_schema: dict[Any, Any] | None = None
    output_schema: dict[Any, Any] | None = None


class WorkflowMetadataError(ValueError):
    pass


def read_resource_frontmatter(file: Path) -> dict[str, Any]:
    text = file.read_text(encoding="utf-8")
    if file.suffix.lower() == ".py":
        return parse_python_frontmatter(text)
    if file.suffix.lower() == ".md":
        return split_markdown_frontmatter(text)[0]
    return {}


def read_workflow_metadata(
    file: Path, frontmatter: dict[str, Any] | None = None
) -> WorkflowMetadata | None:
    metadata = read_resource_frontmatter(file) if frontmatter is None else frontmatter
    resource_type = metadata.get("type")
    if not isinstance(resource_type, str) or resource_type.strip().lower() != "workflow":
        return None

    suffix = file.suffix.lower()
    if suffix == ".py":
        usage = metadata.get("usage")
        if usage is not None and not isinstance(usage, str):
            _invalid(file, "usage", usage, "string")
        return WorkflowMetadata(format="python", usage=usage)

    if suffix == ".md":
        input_schema = _mapping_field(file, metadata, "input")
        output_schema = _mapping_field(file, metadata, "output")
        return WorkflowMetadata(
            format="markdown",
            input_schema=input_schema,
            output_schema=output_schema,
        )

    return None


def _mapping_field(
    file: Path, metadata: dict[str, Any], field: str
) -> dict[Any, Any] | None:
    value = metadata.get(field)
    if value is not None and not isinstance(value, dict):
        _invalid(file, field, value, "mapping")
    return value


def _invalid(file: Path, field: str, value: Any, expected: str):
    raise WorkflowMetadataError(
        f"Invalid workflow metadata in {file}: field '{field}' has type "
        f"{type(value).__name__}; expected {expected}."
    )
