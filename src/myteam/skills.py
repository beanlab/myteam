import subprocess
import sys
from pathlib import Path

from . import templates
from .frontmatter import split_markdown_frontmatter
from .prompt_rendering import render_markdown_body

ENCODING = "utf-8"


def _load_markdown_skill(skill_file: Path) -> str:
    _, content = split_markdown_frontmatter(skill_file.read_text(encoding=ENCODING))
    return render_markdown_body(content, source_path=skill_file)


def _load_python_skill(skill_file: Path) -> str:
    result = subprocess.run(
        [sys.executable, str(skill_file.absolute())],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        raise SystemExit(result.returncode)
    return result.stdout


def _load_skill(skill_file: Path) -> str:
    if skill_file.is_dir():
        print(
            f"Skill '{skill_file}' is a folder. Use 'myteam list {skill_file}' to list it instead.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    suffix = skill_file.suffix.lower()
    if suffix == ".md":
        return _load_markdown_skill(skill_file)
    if suffix == ".py":
        return _load_python_skill(skill_file)

    print(f"Skill '{skill_file}' has unsupported extension '{skill_file.suffix}'.", file=sys.stderr)
    raise SystemExit(1)


def load_skill(skill: str) -> str:
    """Return the instructions for the given skill if available."""
    skill_file = Path(skill)
    return _load_skill(skill_file)


def _write_description(directory: Path) -> None:
    (directory / "description.md").write_text(templates.get_template("folder_description.md"), encoding=ENCODING)


def _skill_exists_error(skill_path: Path) -> None:
    print(f"Skill '{skill_path}' already exists at {skill_path}", file=sys.stderr)
    raise SystemExit(1)


def _ensure_parent_directories(directory: Path, *, parents: bool) -> None:
    if directory.exists():
        if not directory.is_dir():
            print(f"Path for '{directory}' is not a directory: {directory}", file=sys.stderr)
            raise SystemExit(1)
        return

    if not parents:
        print(f"Path for '{directory}' is not a directory: {directory}", file=sys.stderr)
        raise SystemExit(1)

    missing: list[Path] = []
    current = directory
    while not current.exists():
        missing.append(current)
        current = current.parent

    if not current.is_dir():
        print(f"Path for '{directory}' is not a directory: {current}", file=sys.stderr)
        raise SystemExit(1)

    for folder in reversed(missing):
        folder.mkdir()
        _write_description(folder)


def new_skill(skill_name: str, parents: bool = False) -> None:
    skill_path = Path(skill_name)

    if skill_path.suffix == "":
        if skill_path.exists():
            _skill_exists_error(skill_path)

        _ensure_parent_directories(skill_path.parent, parents=parents)
        skill_path.mkdir()
        _write_description(skill_path)
        print("File", skill_path.absolute() / "description.md", "created")
        return

    suffix = skill_path.suffix.lower()
    if suffix == ".md":
        if skill_path.exists():
            _skill_exists_error(skill_path)

        _ensure_parent_directories(skill_path.parent, parents=parents)
        skill_path.write_text(templates.get_template("new_skill.md"), encoding=ENCODING)
        print("File", skill_path.absolute(), "created")
        return
    if suffix == ".py":
        if skill_path.exists():
            _skill_exists_error(skill_path)

        _ensure_parent_directories(skill_path.parent, parents=parents)
        skill_path.write_text(templates.get_template("new_skill.py"), encoding=ENCODING)
        print("File", skill_path.absolute(), "created")
        return

    print(f"Skill '{skill_name}' has unsupported extension '{skill_path.suffix}'.", file=sys.stderr)
    raise SystemExit(1)
