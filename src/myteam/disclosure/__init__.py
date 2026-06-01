from __future__ import annotations

import ast
import os
import subprocess
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Callable, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..paths import BUILTIN_ROOT_NAME, DEFAULT_LOCAL_ROOT, SUPPORTED_TASK_SUFFIXES, base_dir, builtin_agents_root, \
    NON_TASK_FILES, task_candidates
from ..templates import get_template


class TaskStepSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    agent: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    input: Any | None = None
    output: dict[str, Any] | None = None
    interactive: bool | None = None
    session_id: str | None = Field(default=None, min_length=1)
    fork: bool | None = None
    extra_args: tuple[str, ...] | None = None
    usage_logging: Literal["none", "summary", "per_model", "verbose"] | None = None
    timeout: int | None = Field(default=None, gt=0)

    @field_validator("extra_args", mode="before")
    @classmethod
    def _coerce_extra_args(cls, value: Any) -> tuple[str, ...] | None:
        if value is None:
            return None
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(value)
        return value


def get_active_myteam_root(cur_dir: Path) -> Path:
    configured_root = os.environ.get(MYTEAM_ROOT_DIR_ENV_VAR_NAME)
    if configured_root:
        return Path(configured_root)
    return get_myteam_root(cur_dir)


def _print_block(text: str) -> None:
    print(text.rstrip("\n") + "\n")


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


def print_text_block(text: str) -> None:
    _print_block(_strip_yaml_frontmatter(text))


def print_instructions(base: Path):
    for file in ["skill.md", "SKILL.md"]:
        instructions_file = base / file
        if instructions_file.exists():
            print_definition_text(instructions_file.read_text(encoding="utf-8"))
            return


def _get_definition_file(folder: Path, definition_stem: str) -> Path | None:
    for candidate in (f"{definition_stem}.md", f"{definition_stem.upper()}.md"):
        definition_file = folder / candidate
        if definition_file.exists():
            return definition_file
    return None


def is_skill_dir(folder: Path) -> bool:
    return folder.is_dir() and _get_definition_file(folder, "skill") is not None


def _parse_yaml_frontmatter(file: Path) -> dict[str, Any]:
    if not file.exists():
        return {}
    if file.suffix == ".py":
        return _parse_python_module_docstring(file)
    text = file.read_text(encoding="utf-8")
    parsed = parse_yaml_frontmatter(text)
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


def resolve_skill_entry(project_root: Path, skill: str) -> tuple[str, str]:
    if skill == BUILTIN_ROOT_NAME or skill.startswith(f"{BUILTIN_ROOT_NAME}/"):
        folder = builtin_skill_dir(skill)
    else:
        folder = project_root / DEFAULT_LOCAL_ROOT / skill

    if not is_skill_dir(folder):
        return skill, ""

    return skill, _get_folder_info(folder, "skill")


def resolve_task_entry(project_root: Path, task: str) -> tuple[str, str]:
    candidates = task_candidates(project_root, task, prefix=DEFAULT_LOCAL_ROOT)
    if not candidates:
        return task, ""

    task_file = candidates[0]
    root = project_root / DEFAULT_LOCAL_ROOT
    return task_file.relative_to(root).as_posix(), format_frontmatter_info(_parse_yaml_frontmatter(task_file))


def resolve_skill_entries(project_root: Path, skills: list[str] | tuple[str, ...] | None) -> list[tuple[
    str, str]] | None:
    if skills is None:
        return None
    return [resolve_skill_entry(project_root, skill) for skill in skills]


def resolve_task_entries(project_root: Path, tasks: list[str] | tuple[str, ...] | None) -> list[tuple[str, str]] | None:
    if tasks is None:
        return None
    return [resolve_task_entry(project_root, task) for task in tasks]


def format_required_input_shape(input_value: Any) -> str:
    lines = ["input:"]
    if isinstance(input_value, dict):
        dumped = yaml.safe_dump(input_value, default_flow_style=False, sort_keys=False).rstrip("\n")
        lines.extend(f"  {line}" for line in dumped.splitlines())
    else:
        lines.append(f"  {input_value}")
    return "\n".join(lines)


def print_definition_text(text: str) -> None:
    frontmatter, body = split_yaml_frontmatter(text)
    info = format_frontmatter_info(frontmatter)
    if info:
        body = body.lstrip("\n")
        if body:
            _print_block(f"{info}\n\n{body}")
        else:
            _print_block(info)
        return

    _print_block(_strip_yaml_frontmatter(text))


def _get_folder_info(folder: Path, definition_stem: str) -> str:
    definition_file = _get_definition_file(folder, definition_stem)
    if definition_file is not None:
        frontmatter_info = format_frontmatter_info(_parse_yaml_frontmatter(definition_file))
        if frontmatter_info:
            return frontmatter_info

    info = folder / "info.md"
    if info.exists():
        return info.read_text(encoding="utf-8").rstrip("\n")
    return ""


def _builtin_skill_dir(skill_path: str) -> Path:
    parts = skill_path.split("/")
    if not parts or parts[0] != BUILTIN_ROOT_NAME:
        return builtin_agents_root().joinpath(*parts)
    return builtin_agents_root().joinpath(*parts[1:])


def _is_under_builtin_root(folder: Path) -> bool:
    try:
        folder.resolve().relative_to(builtin_agents_root().resolve())
        return True
    except ValueError:
        return False


def is_builtin_skill_dir(folder: Path) -> bool:
    return is_skill_dir(folder) and _is_under_builtin_root(folder)


def builtin_skill_dir(skill_path: str) -> Path:
    return _builtin_skill_dir(skill_path)


def has_builtin_skill(skill_path: str) -> bool:
    return is_builtin_skill_dir(_builtin_skill_dir(skill_path))


def _builtin_root_info() -> str:
    return _get_folder_info(builtin_agents_root(), "skill")


def _is_py_file(file: Path) -> bool:
    return file.is_file() and file.suffix == ".py"


def _print_info(
        header: str,
        folder: Path,
        base_dir: Path,
        ignore: list[str],
        is_relevant: Callable[[Path], bool],
        get_info: Callable[[Path], str],
):
    relevant = list(sorted((p for p in folder.iterdir() if is_relevant(p) and p.name not in ignore)))
    if not relevant:
        return

    print()
    print(f" {header} ".center(30, "*"))
    for cur_dir in relevant:
        name = cur_dir.relative_to(base_dir).as_posix()
        print(f" {name} ".center(30, "-"))
        if info := get_info(cur_dir):
            print(info)
    print()


def _print_named_info(header: str, entries: list[tuple[str, str]]) -> None:
    block = format_named_info_block(header, entries)
    if not block:
        return

    print()
    print(block)
    print()


def format_named_info_block(header: str, entries: list[tuple[str, str]]) -> str:
    if not entries:
        return ""

    lines = [f" {header} ".center(30, "*")]
    for name, info in entries:
        lines.append(f" {name} ".center(30, "-"))
        if info:
            lines.append(info)
    return "\n".join(lines)


def _collect_skill_entries(folder: Path, base_dir: Path, ignore: list[str], *, include_info: bool) -> list[
    tuple[str, str]]:
    effective_ignore = list(ignore)
    entries: list[tuple[str, str]] = []
    if folder == base_dir and not _is_under_builtin_root(folder):
        effective_ignore.append(BUILTIN_ROOT_NAME)

    if folder.exists():
        for skill_dir in sorted(
                (path for path in folder.iterdir() if is_skill_dir(path) and path.name not in effective_ignore),
                key=lambda path: path.name,
        ):
            name = skill_dir.relative_to(base_dir).as_posix()
            entries.append((name, _get_folder_info(skill_dir, "skill") if include_info else ""))

    if include_info and folder == base_dir and not _is_under_builtin_root(folder) and has_builtin_skill(
            BUILTIN_ROOT_NAME):
        entries.append((BUILTIN_ROOT_NAME, _builtin_root_info()))

    if not include_info and folder == base_dir and not _is_under_builtin_root(folder) and has_builtin_skill(
            BUILTIN_ROOT_NAME):
        entries.append((BUILTIN_ROOT_NAME, ""))

    return entries


def collect_skill_names(folder: Path, base_dir: Path, ignore: list[str]) -> list[str]:
    return [name for name, _ in _collect_skill_entries(folder, base_dir, ignore, include_info=False)]


def _collect_task_entries(folder: Path, base_dir: Path, ignore: list[str], *, include_info: bool) -> list[
    tuple[str, str]]:
    effective_ignore = {name.lower() for name in ignore}
    entries: list[tuple[str, str]] = []

    def _visit(current: Path) -> None:
        for path in sorted(current.iterdir(), key=lambda path: (not path.is_dir(), path.name.lower(), path.name)):
            if path.name.lower() in effective_ignore:
                continue
            if path.is_dir():
                _visit(path)
                continue
            if not _is_task_file(path):
                continue

            name = path.relative_to(base_dir).as_posix()
            if include_info:
                info = format_frontmatter_info(_parse_yaml_frontmatter(path))
            else:
                info = ""
            entries.append((name, info))

    if folder.exists():
        _visit(folder)

    return entries


def collect_task_names(folder: Path, base_dir: Path, ignore: list[str]) -> list[str]:
    effective_ignore = {name.lower() for name in ignore}
    names: list[str] = []
    if not folder.exists():
        return names

    for path in sorted(folder.iterdir(), key=lambda path: (not path.is_dir(), path.name.lower(), path.name)):
        if path.name.lower() in effective_ignore:
            continue
        if not _is_task_file(path):
            continue
        names.append(path.relative_to(base_dir).as_posix())
    return names


def _resolve_listing_root(directory: Path | str | None) -> tuple[Path, Path]:
    cwd = base_dir()
    root = get_active_myteam_root(cwd)
    if root == cwd and (cwd / DEFAULT_LOCAL_ROOT).is_dir():
        root = cwd / DEFAULT_LOCAL_ROOT
    if directory is None:
        return root, root

    folder = Path(directory)
    if not folder.is_absolute():
        folder = root / folder
    return folder, root


def _matches_tree_glob(path: Path, root: Path, glob: str) -> bool:
    return path.relative_to(root).match(glob)


def _is_excluded_tree_path(path: Path, root: Path, exclude: tuple[str, ...]) -> bool:
    relative_path = path.relative_to(root).as_posix()
    return any(fnmatch(path.name, pattern) or fnmatch(relative_path, pattern) for pattern in exclude)


def _get_git_ignored_paths(root: Path) -> set[str]:
    try:
        repo_root_text = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return set()

    repo_root = Path(repo_root_text)
    try:
        relative_root = root.relative_to(repo_root)
    except ValueError:
        return set()

    pathspec = relative_root.as_posix()
    if not pathspec:
        pathspec = "."

    try:
        output = subprocess.check_output(
            [
                "git",
                "-C",
                str(repo_root),
                "ls-files",
                "--ignored",
                "--exclude-standard",
                "--others",
                "--directory",
                pathspec,
            ],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return set()

    ignored: set[str] = set()
    prefix = "" if pathspec == "." else f"{pathspec.rstrip('/')}/"
    for line in output.splitlines():
        normalized = line.rstrip("/")
        if prefix and normalized.startswith(prefix):
            normalized = normalized.removeprefix(prefix)
        ignored.add(normalized)
    return ignored


def _is_git_ignored_tree_path(path: Path, root: Path, ignored_paths: set[str]) -> bool:
    relative_path = path.relative_to(root).as_posix()
    for ignored in ignored_paths:
        if relative_path == ignored or relative_path.startswith(f"{ignored}/"):
            return True
    return False


def _collect_tree_entries(
        root: Path,
        folder: Path,
        glob: str,
        max_levels: int | None,
        level: int,
        exclude: tuple[str, ...],
        ignored_paths: set[str],
) -> list[tuple[Path, list[tuple[Path, list]]]]:
    entries: list[tuple[Path, list[tuple[Path, list]]]] = []
    children = sorted(folder.iterdir(), key=lambda path: (not path.is_dir(), path.name.lower(), path.name))

    for child in children:
        if _is_excluded_tree_path(child, root, exclude):
            continue
        if ignored_paths and _is_git_ignored_tree_path(child, root, ignored_paths):
            continue

        if child.is_dir():
            if max_levels is not None and level > max_levels:
                continue

            descendants: list[tuple[Path, list[tuple[Path, list]]]] = []
            if max_levels is None or level < max_levels:
                descendants = _collect_tree_entries(root, child, glob, max_levels, level + 1, exclude, ignored_paths)

            if descendants or glob == "*":
                entries.append((child, descendants))
            continue

        if max_levels is not None and level > max_levels:
            continue
        if _matches_tree_glob(child, root, glob):
            entries.append((child, []))

    return entries


def _print_tree_entries(entries: list[tuple[Path, list[tuple[Path, list]]]], prefix: str) -> None:
    for index, (path, children) in enumerate(entries):
        is_last = index == len(entries) - 1
        branch = "\\-- " if is_last else "|-- "
        extension = "    " if is_last else "|   "
        print(f"{prefix}{branch}{path.name}")
        if children:
            _print_tree_entries(children, prefix + extension)


def print_directory_tree(
        root: Path,
        glob: str = "*",
        max_levels: int | None = None,
        exclude: tuple[str, ...] = (".*", "_*"),
        use_gitignore: bool = True,
        relative_to: Path | None = None,
) -> None:
    root = root.resolve()
    header = root.name or root.as_posix()
    if relative_to is not None:
        header = root.relative_to(relative_to.resolve()).as_posix()

    print(header)
    ignored_paths = _get_git_ignored_paths(root) if use_gitignore else set()
    _print_tree_entries(_collect_tree_entries(root, root, glob, max_levels, 1, exclude, ignored_paths), "")
    print()


def list_roles(folder: Path, base_dir: Path, ignore: list[str]):
    _print_info("Team Members", folder, base_dir, ignore, is_role_dir,
                lambda role_dir: _get_folder_info(role_dir, "role"))


def get_skills(folder: Path, base_dir: Path, ignore: list[str]):
    _print_named_info("Skills", _collect_skill_entries(folder, base_dir, ignore, include_info=True))


def _is_task_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_TASK_SUFFIXES and path.name.lower() not in NON_TASK_FILES


def get_tasks(folder: Path, base_dir: Path, ignore: list[str]):
    _print_named_info("Tasks", _collect_task_entries(folder, base_dir, ignore, include_info=True))


def explain_skills():
    _print_block(get_template("explain_skills.md"))


def explain_tasks():
    _print_block(get_template("explain_tasks.md"))


def explain_roles():
    _print_block(get_template("explain_roles.md"))
