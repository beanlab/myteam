from __future__ import annotations

import ast
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



