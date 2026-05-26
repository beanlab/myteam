from __future__ import annotations

from pathlib import Path
from typing import Any

from ..disclosure import WorkflowStepSettings
from .models import StepResult
from .steps import AgentContext


def run_default_workflow(
        prompt: str,
        *,
        cwd: Path,
        workflow_settings: WorkflowStepSettings | None = None,
) -> StepResult:
    with AgentContext(
            cwd=cwd,
            usage_logging=workflow_settings.usage_logging if workflow_settings is not None else None,
            inactivity_timeout_seconds=(
                workflow_settings.inactivity_timeout_seconds if workflow_settings is not None else None
            ),
    ) as ctx:
        run_kwargs: dict[str, Any] = {"prompt": prompt}
        if workflow_settings is not None:
            if workflow_settings.output is not None:
                run_kwargs["output"] = workflow_settings.output
            if workflow_settings.input is not None:
                run_kwargs["input"] = workflow_settings.input
            if workflow_settings.agent is not None:
                run_kwargs["agent"] = workflow_settings.agent
            if workflow_settings.model is not None:
                run_kwargs["model"] = workflow_settings.model
            if workflow_settings.interactive is not None:
                run_kwargs["interactive"] = workflow_settings.interactive
            if workflow_settings.session_id is not None:
                run_kwargs["session_id"] = workflow_settings.session_id
            if workflow_settings.fork is not None:
                run_kwargs["fork"] = workflow_settings.fork
            if workflow_settings.extra_args is not None:
                run_kwargs["extra_args"] = list(workflow_settings.extra_args)
        return ctx.run_agent(**run_kwargs)
