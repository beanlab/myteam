from __future__ import annotations

from pathlib import Path
from typing import Any

from ...disclosure import WorkflowStepSettings
from ..execution.steps import AgentContext
from .models import StepResult


def _workflow_settings_kwargs(workflow_settings: WorkflowStepSettings | None) -> dict[str, Any]:
    if workflow_settings is None:
        return {}

    kwargs: dict[str, Any] = {
        "output": workflow_settings.output,
        "input": workflow_settings.input,
        "agent": workflow_settings.agent,
        "model": workflow_settings.model,
        "interactive": workflow_settings.interactive,
        "session_id": workflow_settings.session_id,
        "fork": workflow_settings.fork,
        "extra_args": list(workflow_settings.extra_args) if workflow_settings.extra_args is not None else None,
    }
    return {key: value for key, value in kwargs.items() if value is not None}


def run_default_workflow(
    prompt: str,
    *,
    cwd: Path,
    workflow_settings: WorkflowStepSettings | None = None,
) -> StepResult:
    with AgentContext(
        cwd=cwd,
        usage_logging=workflow_settings.usage_logging if workflow_settings is not None else None,
        timeout=(
            workflow_settings.timeout if workflow_settings is not None else None
        ),
    ) as ctx:
        run_kwargs: dict[str, Any] = {"prompt": prompt}
        run_kwargs.update(_workflow_settings_kwargs(workflow_settings))
        return ctx.run_agent(**run_kwargs)
