from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
import importlib.util
import os
from pathlib import Path
from types import ModuleType
from typing import Any, Iterator

from ...disclosure import (
    PROJECT_ROOT_ENV_VAR,
    is_role_dir,
    is_skill_dir,
    load_definition_workflow_settings,
)
from ...paths import DEFAULT_LOCAL_ROOT, agents_root, base_dir
from ..definition.default_workflow import run_default_workflow
from ..definition.models import StepResult
from ..definition.parser import load_workflow
from .engine import run_workflow


@dataclass(frozen=True)
class NamedWorkflowRunResult:
    status: str
    output: Any | None = None
    error_message: str | None = None
    failed_step_name: str | None = None


def run_named_workflow(
    workflow: str | None,
    *,
    input: Any = None,
    prefix: str = DEFAULT_LOCAL_ROOT,
    logger=None,
) -> NamedWorkflowRunResult:
    project_root = _resolve_named_workflow_root(prefix=prefix)

    if workflow is None:
        if not is_role_dir(project_root):
            return NamedWorkflowRunResult(status="failed", error_message="Not a role: None")
        return _run_named_role_or_skill(
            workflow="<root role>",
            folder=project_root,
            dir_type="role",
            project_root=project_root,
            input=input,
        )

    try:
        path = _workflow_target(project_root, workflow)
    except ValueError as exc:
        return NamedWorkflowRunResult(status="failed", error_message=str(exc))
    if path is not None:
        if logger is not None:
            logger(f"Resolved workflow '{workflow}' to {path}")
        if path.suffix == ".py":
            return _run_python_child_workflow(path, workflow=workflow, project_root=project_root, input=input)
        return _run_yaml_child_workflow(path, workflow=workflow, logger=logger)

    folder = project_root.joinpath(*workflow.split("/"))
    if is_role_dir(folder):
        return _run_named_role_or_skill(
            workflow=workflow,
            folder=folder,
            dir_type="role",
            project_root=project_root,
            input=input,
        )
    if is_skill_dir(folder):
        return _run_named_role_or_skill(
            workflow=workflow,
            folder=folder,
            dir_type="skill",
            project_root=project_root,
            input=input,
        )

    return NamedWorkflowRunResult(status="failed", error_message=f"Workflow '{workflow}' not found.")


def _resolve_named_workflow_root(*, prefix: str = DEFAULT_LOCAL_ROOT) -> Path:
    cwd = base_dir().resolve()
    for candidate in (cwd, *cwd.parents):
        if candidate.name == prefix and candidate.is_dir():
            return candidate
    return agents_root(cwd, prefix)


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
        raise ValueError(f"Workflow '{workflow}' is ambiguous. Matching files: {matches}")
    if candidates:
        return candidates[0]
    return None


def _run_yaml_child_workflow(path: Path, *, workflow: str, logger) -> NamedWorkflowRunResult:
    try:
        workflow_definition = load_workflow(path)
        result = run_workflow(workflow_definition, logger=logger)
    except (OSError, ValueError) as exc:
        return NamedWorkflowRunResult(status="failed", error_message=f"Failed to load workflow '{workflow}': {exc}")

    return NamedWorkflowRunResult(
        status=result.status,
        output=result.output,
        error_message=result.error_message,
        failed_step_name=result.failed_step_name,
    )


def _run_named_role_or_skill(
    *,
    workflow: str,
    folder: Path,
    dir_type: str,
    project_root: Path,
    input: Any,
) -> NamedWorkflowRunResult:
    try:
        workflow_settings = load_definition_workflow_settings(folder, dir_type)
        prompt = _load_prompt(folder, workflow, dir_type=dir_type, project_root=project_root)
        child_input = _validate_input(
            workflow_settings.input if workflow_settings is not None else None,
            input,
            workflow=workflow,
            dir_type=dir_type,
        )
        if isinstance(child_input, dict):
            prompt = _format_prompt(prompt, child_input)
        if workflow_settings is not None and child_input is not None:
            workflow_settings = replace(workflow_settings, input=child_input)
        result = run_default_workflow(
            prompt,
            cwd=folder,
            workflow_settings=workflow_settings,
        )
    except (OSError, ValueError, SystemExit) as exc:
        return NamedWorkflowRunResult(status="failed", error_message=str(exc))

    if result.status != "completed":
        return NamedWorkflowRunResult(status="failed", error_message=result.error_message)
    return NamedWorkflowRunResult(
        status="completed",
        output=result.output if result.output is not None else {"status": "completed"},
    )


def _run_python_child_workflow(
    path: Path,
    *,
    workflow: str,
    project_root: Path,
    input: Any,
) -> NamedWorkflowRunResult:
    try:
        if input is not None and not isinstance(input, dict):
            return NamedWorkflowRunResult(
                status="failed",
                error_message=f"Input for Python workflow '{workflow}' must be a mapping.",
            )
        with _temporary_python_workflow_context(path, project_root=project_root):
            module = _load_module_from_path(path)
            main = getattr(module, "main", None)
            if not callable(main):
                return NamedWorkflowRunResult(
                    status="failed",
                    error_message=f"Python workflow '{workflow}' does not define callable main().",
                )
            output = main(**input) if isinstance(input, dict) else main()
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt):
            raise
        return NamedWorkflowRunResult(
            status="failed",
            error_message=f"Python workflow '{workflow}' failed: {exc}",
        )

    if isinstance(output, StepResult):
        return NamedWorkflowRunResult(
            status=output.status,
            output=output.output,
            error_message=output.error_message,
        )

    return NamedWorkflowRunResult(
        status="completed",
        output=output if output is not None else {"status": "completed"},
    )


def _load_prompt(name_dir: Path, name: str | None, *, dir_type: str, project_root: Path) -> str:
    from ..commands import _run_load_py

    result = _run_load_py(dir_type, name_dir, name, project_root=project_root)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return result.stdout or ""


def _validate_input(
    required_input: dict[str, Any] | None,
    input_value: Any,
    *,
    workflow: str,
    dir_type: str,
) -> Any:
    if required_input is None:
        return input_value
    if not isinstance(input_value, dict):
        raise ValueError(f"Input for {dir_type} '{workflow}' must be a mapping.")
    missing = [key for key in required_input if key not in input_value]
    if missing:
        missing_text = ", ".join(str(key) for key in missing)
        raise ValueError(f"Input for {dir_type} '{workflow}' is missing required keys: {missing_text}.")
    return input_value


def _format_prompt(prompt: str, input_value: dict[str, Any]) -> str:
    return prompt.format(**input_value)


def _load_module_from_path(path: Path) -> ModuleType:
    module_name = f"_myteam_child_workflow_{path.stem}_{abs(hash(path))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not create import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def _temporary_python_workflow_context(path: Path, *, project_root: Path) -> Iterator[None]:
    previous_cwd = Path.cwd()
    previous_project_root = os.environ.get(PROJECT_ROOT_ENV_VAR)
    os.environ[PROJECT_ROOT_ENV_VAR] = str(project_root)
    os.chdir(path.parent)
    try:
        yield
    finally:
        os.chdir(previous_cwd)
        if previous_project_root is None:
            os.environ.pop(PROJECT_ROOT_ENV_VAR, None)
        else:
            os.environ[PROJECT_ROOT_ENV_VAR] = previous_project_root
