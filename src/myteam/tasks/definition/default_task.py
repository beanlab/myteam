from __future__ import annotations

from pathlib import Path
from typing import Any

from ...disclosure import TaskStepSettings
from ..execution.steps import AgentContext
from .models import StepResult


def _task_settings_kwargs(task_settings: TaskStepSettings | None) -> dict[str, Any]:
    if task_settings is None:
        return {}

    kwargs: dict[str, Any] = {
        "output": task_settings.output,
        "input": task_settings.input,
        "agent": task_settings.agent,
        "model": task_settings.model,
        "interactive": task_settings.interactive,
        "session_id": task_settings.session_id,
        "fork": task_settings.fork,
        "extra_args": task_settings.extra_args,
    }
    return {key: value for key, value in kwargs.items() if value is not None}


def run_default_task(
    prompt: str,
    *,
    cwd: Path,
    task_settings: TaskStepSettings | None = None,
) -> StepResult:
    with AgentContext(
        cwd=cwd,
        usage_logging=task_settings.usage_logging if task_settings is not None else None,
        timeout=(
            task_settings.timeout if task_settings is not None else None
        ),
    ) as ctx:
        run_kwargs: dict[str, Any] = {"prompt": prompt}
        run_kwargs.update(_task_settings_kwargs(task_settings))
        return ctx.run_agent(**run_kwargs)
