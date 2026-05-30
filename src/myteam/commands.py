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
from .disclosure import (
    PROJECT_ROOT_ENV_VAR,
    builtin_skill_dir,
    format_required_input_shape,
    is_role_dir,
    is_skill_dir,
    print_definition_text,
    split_yaml_frontmatter,
    get_skills as disclose_get_skills,
    get_tasks as disclose_get_tasks,
    WorkflowStepSettings,
)
from .paths import (
    APP_NAME,
    BUILTIN_ROOT_NAME,
    DEFAULT_LOCAL_ROOT,
    ENCODING,
    SUPPORTED_WORKFLOW_SUFFIXES,
    agents_root,
    base_dir,
    role_dir,
    workflow_candidates,
)
from .rosters import download_roster, list_available_rosters, update_roster
from .templates import get_template
from .upgrade import packaged_changelog_text, write_tracked_version
from .tasks.definition.default_task import run_default_workflow
from .tasks.definition.parser import load_markdown_workflow, load_workflow
from .tasks.execution.cli_commands import task_result as submit_task_result
from .tasks.execution.cli_commands import task_start as submit_task_start
from .tasks.execution.engine import run_workflow


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_py_script(path: Path, contents: str) -> None:
    path.write_text(contents, encoding=ENCODING)


def _selected_root(prefix: str | None) -> Path:
    try:
        return agents_root(base_dir(), prefix)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)


def new_dir(
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

    ensure_dir(name_dir)
    rendered_instruction = _set_template_name(instruction_text, name)
    (name_dir / f"{dir_type}.md").write_text(rendered_instruction, encoding=ENCODING)
    write_py_script(name_dir / "load.py", load_text)


def init(prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    """Initialize the myteam directory with default role."""
    root = _selected_root(prefix)
    new_dir(
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


def new_role(role: str, prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    """Create a new role directory with placeholder files."""
    new_dir(
        _selected_root(prefix),
        "role",
        role.split("/"),
        get_template("role_definition_template.md"),
        get_template("role_load_template.py"),
    )


def new_skill(skill: str, prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    if skill == BUILTIN_ROOT_NAME or skill.startswith(f"{BUILTIN_ROOT_NAME}/"):
        print(f"Skill path '{skill}' uses the reserved built-in namespace '{BUILTIN_ROOT_NAME}'.", file=sys.stderr)
        raise SystemExit(1)
    new_dir(
        _selected_root(prefix),
        "skill",
        skill.split("/"),
        get_template("skill_definition_template.md"),
        get_template("skill_load_template.py"),
    )


def new_task(task: str, prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    task_path = Path(task)
    suffix = task_path.suffix
    if not suffix:
        print(
            f"Task '{task}' must include a file extension: .py, .md, .yaml, or .yml.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if suffix not in SUPPORTED_WORKFLOW_SUFFIXES:
        print(f"Task '{task}' has unsupported extension '{suffix}'.", file=sys.stderr)
        raise SystemExit(1)

    task_root = _selected_root(prefix)
    task_path = task_root.joinpath(*task_path.parts)
    if task_path.exists():
        print(f"Task '{task}' already exists at {task_path}", file=sys.stderr)
        raise SystemExit(1)

    ensure_dir(task_path.parent)
    if suffix == ".py":
        template = get_template("task_definition_template.py")
        template = template.removesuffix("\n")
        write_py_script(task_path, template)
        return
    if suffix == ".md":
        template = get_template("task_definition_template.md")
        template = _set_template_name(template, task_path.relative_to(task_root).with_suffix("").as_posix())
        task_path.write_text(template, encoding=ENCODING)
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


def get_name(dir_type: str, name_dir: Path, name: str | None, *, project_root: Path) -> None:
    try:
        result = _run_load_py(dir_type, name_dir, name, project_root=project_root)
    except OSError as exc:
        print(f"Failed to execute load.py for {dir_type} '{name}': {exc}", file=sys.stderr)
        raise SystemExit(1)

    if result.stdout:
        sys.stdout.write(result.stdout)
    raise SystemExit(result.returncode)


def _run_load_py(
        dir_type: str,
        name_dir: Path,
        name: str | None,
        *,
        project_root: Path,
) -> subprocess.CompletedProcess[str]:
    if not name_dir.exists():
        print(
            f"{dir_type.title()} '{name}' not found. Run 'myteam new {dir_type} {name}' to create it.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    load_py = name_dir / "load.py"
    if not load_py.exists():
        print(f"No load.py found for {dir_type} '{name}'.", file=sys.stderr)
        raise SystemExit(1)

    env = dict(os.environ)
    env[PROJECT_ROOT_ENV_VAR] = str(project_root)
    return subprocess.run(
        [sys.executable, str(load_py)],
        cwd=name_dir,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
    )


def get_role(role: str | None = None, prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    """Print the instructions for the given role if available."""
    project_root = _selected_root(prefix)
    folder = project_root
    if role is not None:
        folder = folder.joinpath(*role.split("/"))

    if not is_role_dir(folder):
        print(f"Not a role: {role}", file=sys.stderr)
        raise SystemExit(1)
    get_name("role", folder, role, project_root=project_root)


def get_skill(skill: str, prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    """Print the instructions for the given skill if available."""
    project_root = _selected_root(prefix)
    if skill == BUILTIN_ROOT_NAME or skill.startswith(f"{BUILTIN_ROOT_NAME}/"):
        folder = builtin_skill_dir(skill)
        if not is_skill_dir(folder):
            print(f"Not a skill: {skill}", file=sys.stderr)
            raise SystemExit(1)
        get_name("skill", folder, skill, project_root=project_root)

    folder = project_root.joinpath(*skill.split("/"))
    if is_skill_dir(folder):
        get_name("skill", folder, skill, project_root=project_root)
    print(f"Not a skill: {skill}", file=sys.stderr)
    raise SystemExit(1)


def get_skills(directory: str | None = None, prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    """Print detailed information for skills available in a directory."""
    project_root = _selected_root(prefix)
    folder = project_root if directory is None else project_root.joinpath(*directory.split("/"))
    if not folder.is_dir():
        print(f"Not a directory: {folder}", file=sys.stderr)
        raise SystemExit(1)

    disclose_get_skills(folder, project_root, [])


def get_tasks(directory: str | None = None, prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    """Print detailed information for tasks available in a directory."""
    project_root = _selected_root(prefix)
    folder = project_root if directory is None else project_root.joinpath(*directory.split("/"))
    if not folder.is_dir():
        print(f"Not a directory: {folder}", file=sys.stderr)
        raise SystemExit(1)

    disclose_get_tasks(folder, project_root, [])


def _resolve_task_file(task: str, *, prefix: str) -> Path:
    _selected_root(prefix)
    candidates = workflow_candidates(base_dir(), task, prefix=prefix)
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


def _run_python_workflow(path: Path, *, project_root: Path) -> int:
    env = dict(os.environ)
    env[PROJECT_ROOT_ENV_VAR] = str(project_root)
    result = subprocess.run([sys.executable, str(path)], cwd=path.parent, env=env, check=False)
    return result.returncode


def _run_python_start_workflow(path: Path, *, workflow: str, project_root: Path) -> None:
    try:
        returncode = _run_python_workflow(path, project_root=project_root)
    except OSError as exc:
        print(f"Failed to execute Python workflow '{workflow}': {exc}", file=sys.stderr)
        raise SystemExit(1)
    if returncode != 0:
        raise SystemExit(returncode)


def _run_yaml_start_workflow(path: Path, *, workflow: str, logger) -> None:
    try:
        workflow_definition = load_workflow(path)
    except (OSError, ValueError) as exc:
        print(f"Failed to load workflow '{workflow}': {exc}", file=sys.stderr)
        raise SystemExit(1)

    logger(f"Loaded workflow with {len(workflow_definition)} step(s)")
    result = run_workflow(workflow_definition, logger=logger)
    if result.status != "completed":
        failed_step = result.failed_step_name or "<unknown>"
        if result.error_message:
            print(
                f"Workflow '{workflow}' failed at step '{failed_step}': {result.error_message}",
                file=sys.stderr,
            )
        else:
            print(f"Workflow '{workflow}' failed at step '{failed_step}'.", file=sys.stderr)
        raise SystemExit(1)


def _run_markdown_start_workflow(path: Path, *, workflow: str, input: Any, logger) -> None:
    try:
        prompt, workflow_settings = load_markdown_workflow(path)
    except (OSError, ValueError) as exc:
        print(f"Failed to load workflow '{workflow}': {exc}", file=sys.stderr)
        raise SystemExit(1)

    if workflow_settings is not None and workflow_settings.input is not None and input is None:
        print(
            f"Workflow '{workflow}' requires input:\n{format_required_input_shape(workflow_settings.input)}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if input is not None:
        workflow_settings = (
            replace(workflow_settings, input=input)
            if workflow_settings is not None
            else WorkflowStepSettings(input=input)
        )

    result = run_default_workflow(prompt, cwd=path.parent, workflow_settings=workflow_settings)
    if result.status != "completed":
        if result.error_message:
            print(f"Workflow '{workflow}' failed: {result.error_message}", file=sys.stderr)
        else:
            print(f"Workflow '{workflow}' failed.", file=sys.stderr)
        raise SystemExit(1)

    logger(f"Workflow '{workflow}' completed successfully.")


def start(
        workflow: str = "agent",
        prefix: str = DEFAULT_LOCAL_ROOT,
        verbose: bool = False,
        input: Any = None,
) -> None:
    logger = _log if verbose else (lambda msg: None)
    project_root = agents_root(base_dir(), prefix)

    folder = project_root.joinpath(*workflow.split("/"))
    requested_path = folder
    if not requested_path.suffix:
        file_candidates = workflow_candidates(base_dir(), workflow, prefix=prefix)
        if file_candidates:
            if len(file_candidates) > 1:
                print(
                    f"Workflow '{workflow}' matched multiple files; prioritizing {file_candidates[0]}.",
                    file=sys.stderr,
                )
            path = file_candidates[0]
            logger(f"Resolved workflow '{workflow}' to {path}")
            if path.suffix == ".py":
                _run_python_start_workflow(path, workflow=workflow, project_root=project_root)
                logger(f"Workflow '{workflow}' completed successfully.")
                return

            if path.suffix == ".md":
                _run_markdown_start_workflow(path, workflow=workflow, input=input, logger=logger)
                return

            _run_yaml_start_workflow(path, workflow=workflow, logger=logger)
            logger(f"Workflow '{workflow}' completed successfully.")
            return
    else:
        try:
            file_candidates = workflow_candidates(base_dir(), workflow, prefix=prefix)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1)
        if file_candidates:
            path = file_candidates[0]
            logger(f"Resolved workflow '{workflow}' to {path}")
            if path.suffix == ".py":
                _run_python_start_workflow(path, workflow=workflow, project_root=project_root)
                logger(f"Workflow '{workflow}' completed successfully.")
                return

            if path.suffix == ".md":
                _run_markdown_start_workflow(path, workflow=workflow, input=input, logger=logger)
                return

            _run_yaml_start_workflow(path, workflow=workflow, logger=logger)
            logger(f"Workflow '{workflow}' completed successfully.")
            return

    print(f"Workflow '{workflow}' not found.", file=sys.stderr)
    raise SystemExit(1)


def task_result(json: str | None = None, text: str | None = None, session_nonce: str | None = None) -> None:
    submit_task_result(json=json, text=text, session_nonce=session_nonce)


def task_start(
    workflow: str,
    json: Any | None = None,
    text: str | None = None,
    session_nonce: str | None = None,
) -> None:
    submit_task_start(workflow, json=json, text=text, session_nonce=session_nonce)


def version() -> str:
    return f"{APP_NAME} {__version__}"


def changelog() -> str:
    return packaged_changelog_text().rstrip()


__all__ = [
    "download_roster",
    "get_role",
    "get_skill",
    "get_skills",
    "get_tasks",
    "get_task",
    "init",
    "list_available_rosters",
    "new_role",
    "new_skill",
    "new_task",
    "remove",
    "start",
    "task_result",
    "update_roster",
    "changelog",
    "task_start",
    "version",
]
