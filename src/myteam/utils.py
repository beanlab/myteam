import subprocess
from fnmatch import fnmatch
from pathlib import Path
from typing import Callable

import yaml

from myteam.templates import get_template


def get_myteam_root(cur_dir: Path):
    d = cur_dir
    while d.parent != d:  # i.e. not at root
        if d.name == '.myteam':
            return d
        d = d.parent
    return cur_dir


def _print_block(text: str) -> None:
    print(text.rstrip('\n') + '\n')


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


def print_instructions(base: Path):
    for file in ['role.md', 'ROLE.md', 'skill.md', 'SKILL.md']:
        instructions_file = base / file
        if instructions_file.exists():
            _print_block(_strip_yaml_frontmatter(instructions_file.read_text(encoding='utf-8')))
            return


def _get_definition_file(folder: Path, definition_stem: str) -> Path | None:
    for candidate in (f"{definition_stem}.md", f"{definition_stem.upper()}.md"):
        definition_file = folder / candidate
        if definition_file.exists():
            return definition_file
    return None


def is_role_dir(folder: Path) -> bool:
    return folder.is_dir() and _get_definition_file(folder, "role") is not None


def is_skill_dir(folder: Path) -> bool:
    return folder.is_dir() and _get_definition_file(folder, "skill") is not None


def _parse_yaml_frontmatter(file: Path) -> dict[str, str]:
    if not file.exists():
        return {}

    lines = file.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}

    frontmatter = "\n".join(lines[1:end])
    try:
        loaded = yaml.safe_load(frontmatter)
    except yaml.YAMLError:
        return {}

    if not isinstance(loaded, dict):
        return {}

    data: dict[str, str] = {}
    for key, value in loaded.items():
        if value is None:
            continue
        data[str(key).lower()] = str(value)

    return data


def _format_frontmatter_info(frontmatter: dict[str, str]) -> str:
    name = frontmatter.get("name", "")
    description = frontmatter.get("description", "")
    if name and description:
        return f"{name}: {description}"
    if name:
        return name
    if description:
        return description
    return ""


def _get_folder_info(folder: Path, definition_stem: str) -> str:
    definition_file = _get_definition_file(folder, definition_stem)
    if definition_file is not None:
        frontmatter_info = _format_frontmatter_info(_parse_yaml_frontmatter(definition_file))
        if frontmatter_info:
            return frontmatter_info

    info = folder / "info.md"
    if info.exists():
        return info.read_text(encoding="utf-8").rstrip('\n')
    return ""


def _is_py_file(file: Path) -> bool:
    return file.is_file() and file.suffix == '.py'


def _print_info(
        header: str,
        folder: Path, base_dir: Path, ignore: list[str],
        is_relevant: Callable[[Path], bool],
        get_info: Callable[[Path], str],
):
    relevant = list(sorted(
        p
        for p in folder.iterdir()
        if is_relevant(p) and p.name not in ignore
    ))
    if not relevant:
        return

    print()
    print(f' {header} '.center(30, '*'))
    for cur_dir in relevant:
        name = cur_dir.relative_to(base_dir).as_posix()
        print(f" {name} ".center(30, '-'))
        if info := get_info(cur_dir):
            print(info)
    print()


def _matches_tree_glob(path: Path, root: Path, glob: str) -> bool:
    return path.relative_to(root).match(glob)


def _is_excluded_tree_path(path: Path, root: Path, exclude: tuple[str, ...]) -> bool:
    relative_path = path.relative_to(root).as_posix()
    return any(
        fnmatch(path.name, pattern) or fnmatch(relative_path, pattern)
        for pattern in exclude
    )


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
    _print_tree_entries(
        _collect_tree_entries(root, root, glob, max_levels, 1, exclude, ignored_paths),
        "",
    )
    print()


def list_roles(folder: Path, base_dir: Path, ignore: list[str]):
    _print_info(
        'Team Members',
        folder,
        base_dir,
        ignore,
        is_role_dir,
        lambda role_dir: _get_folder_info(role_dir, "role"),
    )


def list_skills(folder: Path, base_dir: Path, ignore: list[str]):
    _print_info(
        'Skills',
        folder,
        base_dir,
        ignore,
        is_skill_dir,
        lambda skill_dir: _get_folder_info(skill_dir, "skill"),
    )


def list_tools(folder: Path, base_dir: Path, ignore: list[str]):
    _print_info('Tools', folder, base_dir, ignore + ['load.py'], _is_py_file, lambda f: '')
    # TODO - get usage from py file


def explain_skills():
    _print_block(get_template('explain_skills.md'))


def explain_roles():
    _print_block(get_template('explain_roles.md'))

def explain_tools():
    _print_block(get_template('explain_tools.md'))
