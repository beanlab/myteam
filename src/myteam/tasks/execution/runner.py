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
    WorkflowStepSettings,
    format_required_input_shape,
)
from ...paths import DEFAULT_LOCAL_ROOT, agents_root, base_dir, workflow_candidates
from ..definition.default_workflow import run_default_workflow
from ..definition.models import StepResult
from ..definition.parser import load_markdown_workflow, load_workflow
from .engine import run_workflow


@dataclass(frozen=True)
class NamedWorkflowRunResult:
    status: str
    output: Any | None = None
    error_message: str | None = None
    failed_step_name: str | None = None


def run_named_workflow(
    workflow: str,
    *,
    input: Any = None,
    prefix: str = DEFAULT_LOCAL_ROOT,
    logger=None,
) -> NamedWorkflowRunResult:
    project_root = _resolve_named_workflow_root(prefix=prefix)

    folder = project_root.joinpath(*workflow.split("/"))
    if not folder.suffix:
        file_candidates = workflow_candidates(_workflow_lookup_base(project_root, prefix=prefix), workflow, prefix=prefix)
        if file_candidates:
            if len(file_candidates) > 1 and logger is not None:
                logger(f"Workflow '{workflow}' matched multiple files; prioritizing {file_candidates[0]}.")
            path = file_candidates[0]
            if logger is not None:
                logger(f"Resolved workflow '{workflow}' to {path}")
            if path.suffix == ".py":
                return _run_python_child_workflow(path, workflow=workflow, project_root=project_root, input=input)
            if path.suffix == ".md":
                return _run_markdown_child_workflow(path, workflow=workflow, input=input, logger=logger)
            return _run_yaml_child_workflow(path, workflow=workflow, logger=logger)
    else:
        try:
            file_candidates = workflow_candidates(_workflow_lookup_base(project_root, prefix=prefix), workflow, prefix=prefix)
        except ValueError as exc:
            return NamedWorkflowRunResult(status="failed", error_message=str(exc))
        if file_candidates:
            path = file_candidates[0]
            if logger is not None:
                logger(f"Resolved workflow '{workflow}' to {path}")
            if path.suffix == ".py":
                return _run_python_child_workflow(path, workflow=workflow, project_root=project_root, input=input)
            if path.suffix == ".md":
                return _run_markdown_child_workflow(path, workflow=workflow, input=input, logger=logger)
            return _run_yaml_child_workflow(path, workflow=workflow, logger=logger)

    return NamedWorkflowRunResult(status="failed", error_message=f"Workflow '{workflow}' not found.")


def _resolve_named_workflow_root(*, prefix: str = DEFAULT_LOCAL_ROOT) -> Path:
    cwd = base_dir().resolve()
    for candidate in (cwd, *cwd.parents):
        if candidate.name == prefix and candidate.is_dir():
            return candidate
    return agents_root(cwd, prefix)


def _workflow_lookup_base(project_root: Path, *, prefix: str = DEFAULT_LOCAL_ROOT) -> Path:
    cwd = base_dir().resolve()
    if project_root.resolve() == cwd and cwd.name == prefix:
        return cwd.parent
    return cwd


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


def _run_markdown_child_workflow(
    path: Path,
    *,
    workflow: str,
    input: Any,
    logger,
) -> NamedWorkflowRunResult:
    try:
        prompt, workflow_settings = load_markdown_workflow(path)
    except (OSError, ValueError) as exc:
        return NamedWorkflowRunResult(status="failed", error_message=f"Failed to load workflow '{workflow}': {exc}")

    if workflow_settings is not None and workflow_settings.input is not None and input is None:
        return NamedWorkflowRunResult(
            status="failed",
            error_message=f"Workflow '{workflow}' requires input:\n{format_required_input_shape(workflow_settings.input)}",
        )

    if input is not None:
        workflow_settings = (
            replace(workflow_settings, input=input)
            if workflow_settings is not None
            else WorkflowStepSettings(input=input)
        )

    result = run_default_workflow(prompt, cwd=path.parent, workflow_settings=workflow_settings)
    if result.status != "completed":
        return NamedWorkflowRunResult(status="failed", error_message=result.error_message)

    if logger is not None:
        logger(f"Workflow '{workflow}' completed successfully.")
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
