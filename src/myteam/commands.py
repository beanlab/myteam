"""Command implementations for the myteam CLI."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .disclosure import (
    PROJECT_ROOT_ENV_VAR,
    builtin_skill_dir,
    is_role_dir,
    is_skill_dir,
    load_definition_workflow_settings,
)
from .paths import (
    APP_NAME,
    BUILTIN_ROOT_NAME,
    DEFAULT_LOCAL_ROOT,
    ENCODING,
    agents_root,
    base_dir,
    role_dir,
)
from .rosters import download_roster, list_available_rosters, update_roster
from .templates import get_template
from .upgrade import packaged_changelog_text, write_tracked_version
from .workflow.default_workflow import run_default_workflow
from .workflow.engine import run_workflow
from .workflow.parser import load_workflow
from .workflow.result_tool import workflow_result as submit_workflow_result


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
    (name_dir / f"{dir_type}.md").write_text(instruction_text, encoding=ENCODING)
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


def new_workflow(workflow: str = "agent", prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    workflow_root = _selected_root(prefix)
    workflow_path = workflow_root.joinpath(*workflow.split("/")).with_suffix(".py")
    if workflow_path.exists():
        print(f"Workflow '{workflow}' already exists at {workflow_path}", file=sys.stderr)
        raise SystemExit(1)

    ensure_dir(workflow_path.parent)
    template = get_template("workflow_definition_template.py").removesuffix("\n")
    write_py_script(workflow_path, template)


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


def _log(message: str) -> None:
    print(message, file=sys.stderr)


def _run_python_workflow(path: Path, *, project_root: Path) -> int:
    env = dict(os.environ)
    env[PROJECT_ROOT_ENV_VAR] = str(project_root)
    result = subprocess.run([sys.executable, str(path)], cwd=path.parent, env=env, check=False)
    return result.returncode


def _run_start_fallback(
        prompt: str,
        *,
        cwd: Path,
        workflow_settings: Any | None = None,
        input: Any = None,
) -> None:
    workflow_kwargs: dict[str, Any] = {}
    if workflow_settings is not None:
        workflow_kwargs = {
            "agent": workflow_settings.agent,
            "model": workflow_settings.model,
            "input": workflow_settings.input,
            "output": workflow_settings.output,
            "interactive": workflow_settings.interactive,
            "session_id": workflow_settings.session_id,
            "fork": workflow_settings.fork,
            "extra_args": list(workflow_settings.extra_args) if workflow_settings.extra_args is not None else None,
            "usage_logging": workflow_settings.usage_logging,
            "inactivity_timeout_seconds": workflow_settings.inactivity_timeout_seconds,
        }
    if input is not None:
        workflow_kwargs["input"] = input
    result = run_default_workflow(prompt, cwd=cwd, **workflow_kwargs)
    if result.status == "completed" or result.error_type == "completion_missing":
        return
    if result.error_message:
        print(result.error_message, file=sys.stderr)
    raise SystemExit(1)


def _workflow_target(project_root: Path, workflow: str) -> Path | None:
    requested_path = project_root.joinpath(*workflow.split("/"))
    if requested_path.suffix in {".yaml", ".yml", ".py"}:
        return requested_path if requested_path.exists() else None

    candidates: list[Path] = []
    for suffix in (".yaml", ".yml", ".py"):
        candidate = requested_path.with_suffix(suffix)
        if candidate.exists():
            candidates.append(candidate)

    if len(candidates) > 1:
        matches = ", ".join(str(path) for path in candidates)
        print(f"Workflow '{workflow}' is ambiguous. Matching files: {matches}", file=sys.stderr)
        raise SystemExit(1)
    if candidates:
        return candidates[0]
    return None


def _load_start_prompt(name_dir: Path, name: str | None, *, dir_type: str, project_root: Path) -> str:
    try:
        result = _run_load_py(dir_type, name_dir, name, project_root=project_root)
    except OSError as exc:
        print(f"Failed to execute load.py for {dir_type} '{name}': {exc}", file=sys.stderr)
        raise SystemExit(1)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return result.stdout or ""


def _format_start_prompt(prompt: str, input_value: Any, *, workflow: str, dir_type: str) -> str:
    if input_value is None:
        return prompt
    if not isinstance(input_value, dict):
        print(
            f"Input for {dir_type} '{workflow}' must be a mapping to format the prompt.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    try:
        return prompt.format(**input_value)
    except (AttributeError, KeyError, IndexError, ValueError) as exc:
        print(
            f"Failed to format prompt for {dir_type} '{workflow}' using input values: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)


def _format_required_input(required_input: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, description in required_input.items():
        if isinstance(description, str) and description.strip():
            parts.append(f"{key} ({description.strip()})")
        else:
            parts.append(str(key))
    return ", ".join(parts)


def _validate_start_input(
        required_input: dict[str, Any] | None,
        input_value: Any,
        *,
        workflow: str,
        dir_type: str,
) -> Any:
    if required_input is None:
        return input_value

    if not isinstance(input_value, dict):
        required = _format_required_input(required_input)
        print(
            f"Workflow settings for {dir_type} '{workflow}' missing required input values: {required}.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    missing = [key for key in required_input if key not in input_value]
    if missing:
        missing_formatted = _format_required_input({key: required_input[key] for key in missing})
        print(
            f"Workflow settings for {dir_type} '{workflow}' missing required input values: {missing_formatted}.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    return input_value


def _run_named_start_fallback(
        *,
        workflow: str,
        folder: Path,
        dir_type: str,
        project_root: Path,
        input: Any = None,
        logger,
) -> None:
    try:
        workflow_settings = load_definition_workflow_settings(folder, dir_type)
    except ValueError as exc:
        print(f"Failed to load workflow settings for {dir_type} '{workflow}': {exc}", file=sys.stderr)
        raise SystemExit(1)

    prompt = _load_start_prompt(folder, workflow, dir_type=dir_type, project_root=project_root)
    start_input = _validate_start_input(
        workflow_settings.input if workflow_settings is not None else None,
        input,
        workflow=workflow,
        dir_type=dir_type,
    )
    if isinstance(start_input, dict):
        prompt = _format_start_prompt(prompt, start_input, workflow=workflow, dir_type=dir_type)

    _run_start_fallback(prompt, cwd=folder, workflow_settings=workflow_settings, input=start_input)
    logger(f"Started {dir_type} '{workflow}' using fallback agent runner.")


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


def start(
        workflow: str | None = None,
        prefix: str = DEFAULT_LOCAL_ROOT,
        verbose: bool = False,
        input: Any = None,
) -> None:
    logger = _log if verbose else (lambda msg: None)
    project_root = agents_root(base_dir(), prefix)

    if workflow is None:
        if not is_role_dir(project_root):
            print("Not a role: None", file=sys.stderr)
            raise SystemExit(1)
        workflow_label = "<root role>"
        try:
            workflow_settings = load_definition_workflow_settings(project_root, "role")
        except ValueError as exc:
            print(f"Failed to load workflow settings for role '{workflow_label}': {exc}", file=sys.stderr)
            raise SystemExit(1)
        prompt = _load_start_prompt(project_root, None, dir_type="role", project_root=project_root)
        start_input = _validate_start_input(
            workflow_settings.input if workflow_settings is not None else None,
            input,
            workflow=workflow_label,
            dir_type="role",
        )
        if isinstance(start_input, dict):
            prompt = _format_start_prompt(prompt, start_input, workflow=workflow_label, dir_type="role")
        _run_start_fallback(prompt, cwd=project_root, workflow_settings=workflow_settings, input=start_input)
        logger("Workflow start fallback completed successfully.")
        return

    path = _workflow_target(project_root, workflow)
    if path is not None:
        logger(f"Resolved workflow '{workflow}' to {path}")
        if path.suffix == ".py":
            _run_python_start_workflow(path, workflow=workflow, project_root=project_root)
            logger(f"Workflow '{workflow}' completed successfully.")
            return

        _run_yaml_start_workflow(path, workflow=workflow, logger=logger)
        logger(f"Workflow '{workflow}' completed successfully.")
        return

    folder = project_root.joinpath(*workflow.split("/"))
    if is_role_dir(folder):
        _run_named_start_fallback(
                workflow=workflow,
                folder=folder,
                dir_type="role",
                project_root=project_root,
                input=input,
                logger=logger,
        )
        return
    if is_skill_dir(folder):
        _run_named_start_fallback(
                workflow=workflow,
                folder=folder,
                dir_type="skill",
                project_root=project_root,
                input=input,
                logger=logger,
        )
        return

    print(f"Workflow '{workflow}' not found.", file=sys.stderr)
    raise SystemExit(1)


def workflow_result(json: str | None = None, text: str | None = None) -> None:
    submit_workflow_result(json=json, text=text)


def version() -> str:
    return f"{APP_NAME} {__version__}"


def changelog() -> str:
    return packaged_changelog_text().rstrip()


__all__ = [
    "download_roster",
    "get_role",
    "get_skill",
    "init",
    "list_available_rosters",
    "new_role",
    "new_skill",
    "new_workflow",
    "remove",
    "start",
    "workflow_result",
    "update_roster",
    "changelog",
    "version",
]
