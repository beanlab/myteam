"""Command implementations for the myteam CLI."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

from . import __version__
from .rosters import download_roster, list_available_rosters, update_roster
from .paths import (
    APP_NAME,
    BUILTIN_ROOT_NAME,
    DEFAULT_LOCAL_ROOT,
    ENCODING,
    SUPPORTED_TASK_SUFFIXES,
    agents_root,
    base_dir,
    role_dir,
    task_candidates,
)
# from .tasks.definition import run_default_task, load_markdown_task, load_task
# from .tasks.execution.cli_commands import task_result as submit_task_result
# from .tasks.execution.cli_commands import task_start as submit_task_start
# from .tasks.execution.engine import run_task
from .templates import get_template
from .upgrade import packaged_changelog_text, write_tracked_version


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_py_script(path: Path, contents: str) -> None:
    path.write_text(contents, encoding=ENCODING)


def _selected_root(prefix: str | None) -> Path:
    try:
        return agents_root(base_dir(), prefix)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)


def _new_dir(
        base: Path,
        dir_type: str,
        name_parts: list[str],
        instruction_text: str,
        load_text: str,
) -> None:
    name_dir = base.joinpath(*name_parts)
    name = "/".join(name_parts)
    if name_dir.exists():
        print(f"{dir_type.title()} '{name}' already exists at {name_dir}", file=sys.stderr)
        raise SystemExit(1)

    _ensure_dir(name_dir)
    rendered_instruction = _set_template_name(instruction_text, name)
    (name_dir / f"{dir_type}.md").write_text(rendered_instruction, encoding=ENCODING)
    _write_py_script(name_dir / "load.py", load_text)


def init(prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    """Initialize the myteam directory with default role."""
    root = _selected_root(prefix)
    _new_dir(
        base_dir(),
        "role",
        list(root.relative_to(base_dir()).parts),
        "",
        get_template("root_role_load_template.py"),
    )
    write_tracked_version(root)

    agents_md = base_dir() / "AGENTS.md"
    if not agents_md.exists():
        agents_md.write_text(get_template("agents_md_template.md"), encoding=ENCODING)


def new_skill(skill: str, prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    if skill == BUILTIN_ROOT_NAME or skill.startswith(f"{BUILTIN_ROOT_NAME}/"):
        print(f"Skill path '{skill}' uses the reserved built-in namespace '{BUILTIN_ROOT_NAME}'.", file=sys.stderr)
        raise SystemExit(1)
    _new_dir(
        _selected_root(prefix),
        "skill",
        skill.split("/"),
        get_template("skill_definition_template.md"),
        get_template("skill_load_template.py"),
    )


def new_workflow(workflow: str, prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    task_path = Path(workflow)
    suffix = task_path.suffix
    if not suffix:
        print(
            f"Task '{workflow}' must include a file extension: .py, .md, .yaml, or .yml.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if suffix not in SUPPORTED_TASK_SUFFIXES:
        print(f"Task '{workflow}' has unsupported extension '{suffix}'.", file=sys.stderr)
        raise SystemExit(1)

    task_root = _selected_root(prefix)
    task_path = task_root.joinpath(*task_path.parts)
    if task_path.exists():
        print(f"Task '{workflow}' already exists at {task_path}", file=sys.stderr)
        raise SystemExit(1)

    _ensure_dir(task_path.parent)
    if suffix == ".py":
        template = get_template("task_definition_template.py")
        template = template.removesuffix("\n")
        _write_py_script(task_path, template)
        return
    if suffix == ".md":
        template = get_template("task_definition_template.md")
        template = _set_template_name(template, task_path.relative_to(task_root).with_suffix("").as_posix())
        task_path.write_text(template, encoding=ENCODING)
        return
    if suffix in {".yaml", ".yml"}:
        task_path.write_text(get_template("task_definition_template.yaml"), encoding=ENCODING)
        return

    task_path.write_text("", encoding=ENCODING)


def _set_template_name(template: str, name: str) -> str:
    frontmatter, body = split_yaml_frontmatter(template)
    frontmatter["name"] = name
    rendered_frontmatter = yaml.safe_dump(frontmatter, sort_keys=False).strip()
    return f"---\n{rendered_frontmatter}\n---\n{body}"


def remove(name: str, prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    """Delete the directory for a role or skill if it exists."""
    target_dir = role_dir(base_dir(), name, prefix)  # TODO fix for skills
    if not target_dir.exists():
        print(f"'{name}' not found at {target_dir}", file=sys.stderr)
        raise SystemExit(1)

    if not target_dir.is_dir():
        print(f"Path for '{name}' is not a directory: {target_dir}", file=sys.stderr)
        raise SystemExit(1)

    try:
        shutil.rmtree(target_dir)
    except OSError as exc:
        print(f"Failed to remove '{name}': {exc}", file=sys.stderr)
        raise SystemExit(1)


def get_workflows(directory: str | None = None, prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    """Print detailed information for tasks available in a directory."""
    project_root = _selected_root(prefix)
    folder = project_root if directory is None else project_root.joinpath(*directory.split("/"))
    if not folder.is_dir():
        print(f"Not a directory: {folder}", file=sys.stderr)
        raise SystemExit(1)

    disclose_get_tasks(folder, project_root, [])


def _resolve_task_file(task: str, *, prefix: str) -> Path:
    _selected_root(prefix)
    candidates = task_candidates(base_dir(), task, prefix=prefix)
    if candidates:
        return candidates[0]

    print(
        f"Task '{task}' not found. Run 'myteam new task {task}' to create it.",
        file=sys.stderr,
    )
    raise SystemExit(1)


def get_task(task: str, prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    """Print the detailed contents for a single task."""
    task_file = _resolve_task_file(task, prefix=prefix)
    print_definition_text(task_file.read_text(encoding=ENCODING))
    raise SystemExit(0)


def _log(message: str) -> None:
    print(message, file=sys.stderr)


def _run_python_task(path: Path, *, project_root: Path) -> int:
    env = dict(os.environ)
    env[MYTEAM_ROOT_DIR_ENV_VAR_NAME] = str(project_root)
    result = subprocess.run([sys.executable, str(path)], cwd=path.parent, env=env, check=False)
    return result.returncode


def _run_python_start_task(path: Path, *, task: str, project_root: Path) -> None:
    try:
        returncode = _run_python_task(path, project_root=project_root)
    except OSError as exc:
        print(f"Failed to execute Python task '{task}': {exc}", file=sys.stderr)
        raise SystemExit(1)
    if returncode != 0:
        raise SystemExit(returncode)


def _run_yaml_start_task(path: Path, *, task: str, logger) -> None:
    try:
        task_definition = load_task(path)
    except (OSError, ValueError) as exc:
        print(f"Failed to load task '{task}': {exc}", file=sys.stderr)
        raise SystemExit(1)

    logger(f"Loaded task with {len(task_definition)} step(s)")
    result = run_task(task_definition, logger=logger)
    if result.status != "completed":
        failed_step = result.failed_step_name or "<unknown>"
        if result.error_message:
            print(
                f"Task '{task}' failed at step '{failed_step}': {result.error_message}",
                file=sys.stderr,
            )
        else:
            print(f"Task '{task}' failed at step '{failed_step}'.", file=sys.stderr)
        raise SystemExit(1)


def _run_markdown_start_task(path: Path, *, task: str, input: Any, logger) -> None:
    try:
        prompt, task_settings = load_markdown_task(path)
    except (OSError, ValueError) as exc:
        print(f"Failed to load task '{task}': {exc}", file=sys.stderr)
        raise SystemExit(1)

    if task_settings is not None and task_settings.input is not None and input is None:
        print(
            f"Task '{task}' requires input:\n{format_required_input_shape(task_settings.input)}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if input is not None:
        task_settings = (
            replace(task_settings, input=input)
            if task_settings is not None
            else TaskStepSettings(input=input)
        )

    result = run_default_task(prompt, cwd=path.parent, task_settings=task_settings)
    if result.status != "completed":
        if result.error_message:
            print(f"Task '{task}' failed: {result.error_message}", file=sys.stderr)
        else:
            print(f"Task '{task}' failed.", file=sys.stderr)
        raise SystemExit(1)

    logger(f"Task '{task}' completed successfully.")


def start_workflow(
        task: str = "agent",
        prefix: str = DEFAULT_LOCAL_ROOT,
        verbose: bool = False,
        input: Any = None,
) -> None:
    logger = _log if verbose else (lambda msg: None)
    project_root = agents_root(base_dir(), prefix)

    folder = project_root.joinpath(*task.split("/"))
    requested_path = folder
    if not requested_path.suffix:
        file_candidates = task_candidates(base_dir(), task, prefix=prefix)
        if file_candidates:
            if len(file_candidates) > 1:
                print(
                    f"Task '{task}' matched multiple files; prioritizing {file_candidates[0]}.",
                    file=sys.stderr,
                )
            path = file_candidates[0]
            logger(f"Resolved task '{task}' to {path}")
            if path.suffix == ".py":
                _run_python_start_task(path, task=task, project_root=project_root)
                logger(f"Task '{task}' completed successfully.")
                return

            if path.suffix == ".md":
                _run_markdown_start_task(path, task=task, input=input, logger=logger)
                return

            _run_yaml_start_task(path, task=task, logger=logger)
            logger(f"Task '{task}' completed successfully.")
            return
    else:
        try:
            file_candidates = task_candidates(base_dir(), task, prefix=prefix)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1)
        if file_candidates:
            path = file_candidates[0]
            logger(f"Resolved task '{task}' to {path}")
            if path.suffix == ".py":
                _run_python_start_task(path, task=task, project_root=project_root)
                logger(f"Task '{task}' completed successfully.")
                return

            if path.suffix == ".md":
                _run_markdown_start_task(path, task=task, input=input, logger=logger)
                return

            _run_yaml_start_task(path, task=task, logger=logger)
            logger(f"Task '{task}' completed successfully.")
            return

    print(f"Task '{task}' not found.", file=sys.stderr)
    raise SystemExit(1)


def task_result(json: str | None = None, text: str | None = None, session_nonce: str | None = None) -> None:
    submit_task_result(json=json, text=text, session_nonce=session_nonce)


def task_start(
        task: str,
        json: Any | None = None,
        text: str | None = None,
        session_nonce: str | None = None,
) -> None:
    submit_task_start(task, json=json, text=text, session_nonce=session_nonce)


def version() -> str:
    return f"{APP_NAME} {__version__}"


def changelog() -> str:
    return packaged_changelog_text().rstrip()


__all__ = [
    "download_roster",
    "get_role",
    "load_skill",
    "get_skills",
    "get_workflows",
    "get_task",
    "init",
    "list_available_rosters",
    "new_role",
    "new_skill",
    "new_workflow",
    "remove",
    "start_workflow",
    "task_result",
    "update_roster",
    "changelog",
    "task_start",
    "version",
]
