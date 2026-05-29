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
    WorkflowStepSettings,
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

    folder = project_root.joinpath(*workflow.split("/"))
    if not folder.suffix:
        directory_matches: list[tuple[str, Path]] = []
        if is_role_dir(folder):
            directory_matches.append(("role", folder))
        if is_skill_dir(folder):
            directory_matches.append(("skill", folder))

        file_candidates = workflow_candidates(_workflow_lookup_base(project_root, prefix=prefix), workflow, prefix=prefix)
        if directory_matches:
            if len(directory_matches) > 1 or file_candidates:
                if logger is not None:
                    logger(
                        f"Workflow '{workflow}' matched multiple targets; prioritizing {directory_matches[0][0]} directory."
                    )
            return _run_named_role_or_skill(
                workflow=workflow,
                folder=directory_matches[0][1],
                dir_type=directory_matches[0][0],
                project_root=project_root,
                input=input,
            )
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
    from ...commands import _run_load_py

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
    if input_value is None or not isinstance(input_value, dict):
        _raise_input_contract_mismatch(
            required_input,
            input_value,
            workflow=workflow,
            dir_type=dir_type,
        )
    missing = [key for key in required_input if key not in input_value]
    if missing:
        _raise_input_contract_mismatch(
            required_input,
            input_value,
            workflow=workflow,
            dir_type=dir_type,
        )
    return input_value


def _raise_input_contract_mismatch(
    required_input: dict[str, Any],
    input_value: Any,
    *,
    workflow: str,
    dir_type: str,
) -> None:
    received = "<none>" if input_value is None else repr(input_value)
    required = _format_required_input(required_input)
    missing = _format_required_input(
        {
            key: required_input[key]
            for key in required_input
            if not isinstance(input_value, dict) or key not in input_value
        }
    )
    unexpected = "<none>"
    if isinstance(input_value, dict):
        unexpected = _format_input_keys({key: input_value[key] for key in input_value if key not in required_input}) or "<none>"
    raise ValueError(
        f"Workflow settings for {dir_type} '{workflow}' input contract mismatch.\n"
        f"{_format_required_input_shape(required_input)}\n"
        f"Received: {received}.\n"
        f"Missing keys: {missing}.\n"
        f"Unexpected keys: {unexpected}."
    )


def _format_required_input(required_input: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, description in required_input.items():
        if isinstance(description, str) and description.strip():
            parts.append(f"{key} ({description.strip()})")
        else:
            parts.append(str(key))
    return ", ".join(parts)


def _format_required_input_shape(required_input: dict[str, Any]) -> str:
    lines = ["Required input shape:"]
    for key, description in required_input.items():
        if isinstance(description, str) and description.strip():
            lines.append(f"  {key}: {description.strip()}")
        else:
            lines.append(f"  {key}: <required>")
    return "\n".join(lines)


def _format_input_keys(input_value: dict[str, Any]) -> str:
    keys = sorted(str(key) for key in input_value)
    return ", ".join(keys)


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
