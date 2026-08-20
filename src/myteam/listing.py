"""Listing helpers for myteam resources."""
from __future__ import annotations

import dataclasses
import errno
import stat
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


def list_resources(*targets: str | Path, directory: bool = False) -> str:
    try:
        root = _current_root()
        requested = targets or (root,)
        selected = _select_targets(root, requested, directory=directory)
        infos = list_resource_entries(root, selected)
    except OSError as exc:
        print(_filesystem_error(exc), file=sys.stderr)
        raise SystemExit(1) from None
    return _format_resource_infos(infos)


def _current_root() -> Path:
    try:
        cwd = Path.cwd()
    except OSError as exc:
        raise OSError(exc.errno, exc.strerror or str(exc), "current directory") from None
    return _resolve_path(cwd)


def _select_targets(root: Path, targets: tuple[str | Path, ...], *, directory: bool) -> list[Path]:
    selected: list[Path] = []
    identities: set[tuple[int, int]] = set()

    for target in targets:
        path = _resolve_target(root, target)
        target_stat = path.stat()
        if stat.S_ISDIR(target_stat.st_mode) and not directory:
            candidates = sorted(path.iterdir(), key=lambda item: (item.name.lower(), item.name))
        else:
            candidates = [path]

        for candidate in candidates:
            canonical = _resolve_path(candidate)
            candidate_stat = canonical.stat()
            identity = (candidate_stat.st_dev, candidate_stat.st_ino)
            if identity not in identities:
                identities.add(identity)
                selected.append(candidate)

    return selected


def list_resource_entries(root: Path, paths: list[Path]) -> list[ResourceInfo]:
    entries: list[ResourceInfo] = []
    for path in paths:
        path_stat = path.stat()
        if stat.S_ISDIR(path_stat.st_mode):
            description = read_folder_description(path)
            if description is not None:
                entries.append(ResourceInfo("folder", f"{_display_name(root, path)}/", description))
            continue
        if not stat.S_ISREG(path_stat.st_mode):
            continue

        metadata = _read_type_description(path)
        if metadata is None:
            continue
        resource_type, description = metadata
        entries.append(ResourceInfo(resource_type, _display_name(root, path), description))

    return sorted(entries, key=_sort_key)


def read_folder_description(folder: Path) -> str | None:
    description_file = folder / "description.md"
    try:
        description_file.stat()
    except FileNotFoundError:
        folder.stat()
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


def _resolve_target(root: Path, target: str | Path) -> Path:
    path = Path(target)
    if not path.is_absolute():
        path = root / path
    return _resolve_path(path)


def _resolve_path(path: Path) -> Path:
    try:
        return path.resolve()
    except RuntimeError:
        raise OSError(errno.ELOOP, "Too many levels of symbolic links", str(path)) from None


def _filesystem_error(exc: OSError) -> str:
    affected = exc.filename or "unknown path"
    cause = exc.strerror or str(exc)
    return f"Unable to list {affected}: {cause}"


def _display_name(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return _resolve_path(path).as_posix()


def _sort_key(info: ResourceInfo) -> tuple[str, str]:
    return info.name.rstrip("/").lower(), info.type


def _format_resource_infos(infos: list[ResourceInfo]) -> str:
    if not infos:
        return ""
    return "\n\n".join(_format_info(info) for info in infos)


def _format_info(info: ResourceInfo) -> str:
    if info.type == "folder":
        header = f"----{info.name}----"
    else:
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
