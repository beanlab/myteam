"""Listing helpers for myteam resources."""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from typing import Literal

from .frontmatter import parse_python_frontmatter, split_markdown_frontmatter

ResourceType = Literal["folder", "skill", "workflow"]


@dataclasses.dataclass(frozen=True)
class ResourceInfo:
    type: ResourceType
    name: str
    description: str


def list_resources(prefix: str | None = None) -> str:
    root = Path.cwd().resolve()
    prefix_path = _resolve_prefix_path(root, prefix)
    return _format_resource_infos(list_resource_entries(root, prefix_path))


def list_resource_entries(root: Path, prefix: Path) -> list[ResourceInfo]:
    if not prefix.exists():
        print(f"Not a directory: {prefix}", file=sys.stderr)
        raise SystemExit(1)
    if not prefix.is_dir():
        print(f"Not a directory: {prefix}", file=sys.stderr)
        raise SystemExit(1)

    entries: list[ResourceInfo] = []
    for item in sorted(prefix.iterdir(), key=lambda path: (path.name.lower(), path.name)):
        if item.is_dir():
            description = read_folder_description(item)
            if description is not None:
                entries.append(ResourceInfo("folder", f"{_display_name(root, item)}/", description))
            continue

        metadata = _read_type_description(item)
        if metadata is None:
            continue

        rtype, description = metadata
        entries.append(ResourceInfo(rtype, _display_name(root, item), description))

    return sorted(entries, key=_sort_key)


def read_folder_description(folder: Path) -> str | None:
    description_file = folder / "description.md"
    if not description_file.exists():
        return None

    text = description_file.read_text(encoding="utf-8")
    _, body = split_markdown_frontmatter(text)
    return body.rstrip("\n")


def _read_type_description(file: Path) -> tuple[Literal["skill", "workflow"], str] | None:
    if file.suffix == ".py":
        return _read_python_type_description(file)
    if file.suffix == ".md":
        return _read_markdown_type_description(file)
    return None


def _read_markdown_type_description(file: Path) -> tuple[Literal["skill", "workflow"], str] | None:
    frontmatter, _ = split_markdown_frontmatter(file.read_text(encoding="utf-8"))
    return _extract_type_description(frontmatter)


def _read_python_type_description(file: Path) -> tuple[Literal["skill", "workflow"], str] | None:
    frontmatter = parse_python_frontmatter(file.read_text(encoding="utf-8"))
    return _extract_type_description(frontmatter)


def _extract_type_description(frontmatter: dict) -> tuple[Literal["skill", "workflow"], str] | None:
    resource_type = frontmatter.get("type")
    if not isinstance(resource_type, str):
        return None

    normalized_type = resource_type.strip().lower()
    if normalized_type not in {"skill", "workflow"}:
        return None

    description = frontmatter.get("description")
    if isinstance(description, str):
        rendered_description = description.strip()
    elif description is None:
        rendered_description = ""
    else:
        rendered_description = str(description)

    return normalized_type, rendered_description


def _resolve_prefix_path(root: Path, prefix: str | None) -> Path:
    if prefix in (None, ""):
        return root

    prefix_path = Path(prefix)
    if not prefix_path.is_absolute():
        prefix_path = root / prefix_path
    return prefix_path.resolve()


def _display_name(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _sort_key(info: ResourceInfo) -> tuple[str, str]:
    return info.name.rstrip("/").lower(), info.type


def _format_resource_infos(infos: list[ResourceInfo]) -> str:
    if not infos:
        return ""
    return "\n\n".join(_format_info(info) for info in infos)


def _format_info(info: ResourceInfo) -> str:
    header = f"----{info.type}: {info.name}----"

    if not info.description:
        return header

    return f"{header}\n{info.description}"


__all__ = [
    "ResourceInfo",
    "list_resource_entries",
    "list_resources",
    "read_folder_description",
]
