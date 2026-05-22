from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import DefaultWorkflowConfig, load_default_workflow_config
from .steps import AgentContext
from .models import StepResult

DEFAULT_AGENT = "codex"
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_USAGE_LOGGING = "summary"
DEFAULT_TIMEOUT_SECONDS = 900


def _resolve_default_workflow_config(cwd: Path) -> DefaultWorkflowConfig:
    return load_default_workflow_config(
        cwd,
        default_agent=DEFAULT_AGENT,
        default_model=DEFAULT_MODEL,
        default_usage_logging=DEFAULT_USAGE_LOGGING,
        default_timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    )


def run_default_workflow(
        prompt: str,
        *,
        cwd: Path,
        agent: str | None = None,
        model: str | None = None,
        output: dict[str, Any] | None = None,
) -> StepResult:
    config = _resolve_default_workflow_config(cwd)
    resolved_agent = config.agent if agent is None else agent
    resolved_model = config.model if model is None else model

    with AgentContext(
            usage_logging=config.usage_logging,
            cwd=cwd,
            inactivity_timeout_seconds=config.inactivity_timeout_seconds,
    ) as ctx:
        return ctx.run_agent(
            agent=resolved_agent,
            model=resolved_model,
            prompt=prompt,
            output={} if output is None else output,
        )
