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
    TaskStepSettings,
    format_required_input_shape,
)
from ...paths import DEFAULT_LOCAL_ROOT, agents_root, base_dir, task_candidates
from ..definition.default_task import run_default_task
from ..definition.models import StepResult
from ..definition.parser import load_markdown_task, load_task
from .engine import run_task


@dataclass(frozen=True)
class NamedTaskRunResult:
    status: str
    output: Any | None = None
    error_message: str | None = None
    failed_step_name: str | None = None


def run_named_task(
    task: str,
    *,
    input: Any = None,
    prefix: str = DEFAULT_LOCAL_ROOT,
    logger=None,
) -> NamedTaskRunResult:
    project_root = _resolve_named_task_root(prefix=prefix)

    folder = project_root.joinpath(*task.split("/"))
    if not folder.suffix:
        file_candidates = task_candidates(_task_lookup_base(project_root, prefix=prefix), task, prefix=prefix)
        if file_candidates:
            if len(file_candidates) > 1 and logger is not None:
                logger(f"Task '{task}' matched multiple files; prioritizing {file_candidates[0]}.")
            path = file_candidates[0]
            if logger is not None:
                logger(f"Resolved task '{task}' to {path}")
            if path.suffix == ".py":
                return _run_python_child_task(path, task=task, project_root=project_root, input=input)
            if path.suffix == ".md":
                return _run_markdown_child_task(path, task=task, input=input, logger=logger)
            return _run_yaml_child_task(path, task=task, logger=logger)
    else:
        try:
            file_candidates = task_candidates(_task_lookup_base(project_root, prefix=prefix), task, prefix=prefix)
        except ValueError as exc:
            return NamedTaskRunResult(status="failed", error_message=str(exc))
        if file_candidates:
            path = file_candidates[0]
            if logger is not None:
                logger(f"Resolved task '{task}' to {path}")
            if path.suffix == ".py":
                return _run_python_child_task(path, task=task, project_root=project_root, input=input)
            if path.suffix == ".md":
                return _run_markdown_child_task(path, task=task, input=input, logger=logger)
            return _run_yaml_child_task(path, task=task, logger=logger)

    return NamedTaskRunResult(status="failed", error_message=f"Task '{task}' not found.")


def _resolve_named_task_root(*, prefix: str = DEFAULT_LOCAL_ROOT) -> Path:
    cwd = base_dir().resolve()
    for candidate in (cwd, *cwd.parents):
        if candidate.name == prefix and candidate.is_dir():
            return candidate
    return agents_root(cwd, prefix)


def _task_lookup_base(project_root: Path, *, prefix: str = DEFAULT_LOCAL_ROOT) -> Path:
    cwd = base_dir().resolve()
    if project_root.resolve() == cwd and cwd.name == prefix:
        return cwd.parent
    return cwd


def _run_yaml_child_task(path: Path, *, task: str, logger) -> NamedTaskRunResult:
    try:
        task_definition = load_task(path)
        result = run_task(task_definition, logger=logger)
    except (OSError, ValueError) as exc:
        return NamedTaskRunResult(status="failed", error_message=f"Failed to load task '{task}': {exc}")

    return NamedTaskRunResult(
        status=result.status,
        output=result.output,
        error_message=result.error_message,
        failed_step_name=result.failed_step_name,
    )


def _run_markdown_child_task(
    path: Path,
    *,
    task: str,
    input: Any,
    logger,
) -> NamedTaskRunResult:
    try:
        prompt, task_settings = load_markdown_task(path)
    except (OSError, ValueError) as exc:
        return NamedTaskRunResult(status="failed", error_message=f"Failed to load task '{task}': {exc}")

    if task_settings is not None and task_settings.input is not None and input is None:
        return NamedTaskRunResult(
            status="failed",
            error_message=f"Task '{task}' requires input:\n{format_required_input_shape(task_settings.input)}",
        )

    if input is not None:
        task_settings = (
            replace(task_settings, input=input)
            if task_settings is not None
            else TaskStepSettings(input=input)
        )

    result = run_default_task(prompt, cwd=path.parent, task_settings=task_settings)
    if result.status != "completed":
        return NamedTaskRunResult(status="failed", error_message=result.error_message)

    if logger is not None:
        logger(f"Task '{task}' completed successfully.")
    return NamedTaskRunResult(
        status="completed",
        output=result.output if result.output is not None else {"status": "completed"},
    )


def _run_python_child_task(
    path: Path,
    *,
    task: str,
    project_root: Path,
    input: Any,
) -> NamedTaskRunResult:
    try:
        if input is not None and not isinstance(input, dict):
            return NamedTaskRunResult(
                status="failed",
                error_message=f"Input for Python task '{task}' must be a mapping.",
            )
        with _temporary_python_task_context(path, project_root=project_root):
            module = _load_module_from_path(path)
            main = getattr(module, "main", None)
            if not callable(main):
                return NamedTaskRunResult(
                    status="failed",
                    error_message=f"Python task '{task}' does not define callable main().",
                )
            output = main(**input) if isinstance(input, dict) else main()
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt):
            raise
        return NamedTaskRunResult(
            status="failed",
            error_message=f"Python task '{task}' failed: {exc}",
        )

    if isinstance(output, StepResult):
        return NamedTaskRunResult(
            status=output.status,
            output=output.output,
            error_message=output.error_message,
        )

    return NamedTaskRunResult(
        status="completed",
        output=output if output is not None else {"status": "completed"},
    )


def _load_module_from_path(path: Path) -> ModuleType:
    module_name = f"_myteam_child_task_{path.stem}_{abs(hash(path))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not create import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def _temporary_python_task_context(path: Path, *, project_root: Path) -> Iterator[None]:
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
