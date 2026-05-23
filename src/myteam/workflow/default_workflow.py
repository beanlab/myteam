from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import DefaultWorkflowConfig, load_default_workflow_config as _load_default_workflow_config
from .agents import DEFAULT_AGENT
from .models import StepResult
from .steps import AgentContext


DEFAULT_MODEL = ""
DEFAULT_USAGE_LOGGING = "summary"
DEFAULT_TIMEOUT_SECONDS = 300


def load_default_workflow_config(
    local_root: Path,
    *,
    default_agent: str = DEFAULT_AGENT,
    default_model: str = DEFAULT_MODEL,
    default_usage_logging: str = DEFAULT_USAGE_LOGGING,
    default_timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> DefaultWorkflowConfig:
    return _load_default_workflow_config(
        local_root,
        default_agent=default_agent,
        default_model=default_model,
        default_usage_logging=default_usage_logging,
        default_timeout_seconds=default_timeout_seconds,
    )


def run_default_workflow(
        prompt: str,
        *,
        cwd: Path,
        agent: str | None = None,
        model: str | None = None,
        output: dict[str, Any] | None = None,
        input: Any = None,
        interactive: bool | None = None,
        session_id: str | None = None,
        fork: bool | None = None,
        extra_args: list[str] | None = None,
        usage_logging: str | None = None,
        inactivity_timeout_seconds: int | None = None,
) -> StepResult:
    with AgentContext(
            cwd=cwd,
            usage_logging=usage_logging,
            inactivity_timeout_seconds=inactivity_timeout_seconds,
    ) as ctx:
        run_kwargs: dict[str, Any] = {"prompt": prompt}
        if output is not None:
            run_kwargs["output"] = output
        if input is not None:
            run_kwargs["input"] = input
        if agent is not None:
            run_kwargs["agent"] = agent
        if model is not None:
            run_kwargs["model"] = model
        if interactive is not None:
            run_kwargs["interactive"] = interactive
        if session_id is not None:
            run_kwargs["session_id"] = session_id
        if fork is not None:
            run_kwargs["fork"] = fork
        if extra_args is not None:
            run_kwargs["extra_args"] = extra_args
        return ctx.run_agent(**run_kwargs)
