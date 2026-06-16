from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import yaml


def parse_python_frontmatter(content: str) -> dict[str, Any]:
    try:
        module = ast.parse(content)
    except (OSError, SyntaxError):
        return {}

    docstring = ast.get_docstring(module, clean=False)
    if not docstring:
        return {}

    return split_markdown_frontmatter(f"---\n{docstring}\n---\n")[0]


def split_markdown_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text

    frontmatter = "\n".join(lines[1:end])
    try:
        loaded = yaml.safe_load(frontmatter)
    except yaml.YAMLError:
        return {}, text

    if not isinstance(loaded, dict):
        return {}, text

    data: dict[str, Any] = {}
    for key, value in loaded.items():
        if value is None:
            continue
        data[str(key).lower()] = value
    body = "\n".join(lines[end + 1:])
    if text.endswith("\n"):
        body += "\n"
    return data, body


def format_frontmatter_info(frontmatter: dict[str, Any]) -> str:
    lines: list[str] = []

    description = frontmatter.get("description")
    if isinstance(description, str) and description.strip():
        lines.append(description.strip())

    input_value = frontmatter.get("input")
    if input_value is not None:
        lines.append("input:")
        if isinstance(input_value, dict):
            for key, value in input_value.items():
                lines.append(f"  {key}: {value}")
        else:
            lines.append(f"  {input_value}")

    return "\n".join(lines)


def _strip_yaml_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text

    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            body = "\n".join(lines[i + 1:])
            if text.endswith("\n"):
                body += "\n"
            return body
    return text


def parse_frontmatter(file: Path) -> dict[str, Any]:
    if not file.exists():
        return {}
    if file.suffix == ".py":
        return _parse_python_module_docstring(file)
    text = file.read_text(encoding="utf-8")
    parsed, _ = split_markdown_frontmatter(text)
    if parsed:
        return parsed

    if file.suffix.lower() in {".yaml", ".yml"}:
        try:
            loaded = yaml.safe_load(text)
        except yaml.YAMLError:
            return {}
        if isinstance(loaded, dict):
            data: dict[str, Any] = {}
            for key, value in loaded.items():
                if value is None:
                    continue
                data[str(key).lower()] = value
            return data
    return {}
