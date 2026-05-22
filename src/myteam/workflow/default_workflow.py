from __future__ import annotations

from pathlib import Path
from typing import Any

from .steps import AgentContext
from .models import StepResult

DEFAULT_AGENT = "codex"
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_USAGE_LOGGING = "summary"
DEFAULT_TIMEOUT_SECONDS = 900


def run_default_workflow(
        prompt: str,
        *,
        cwd: Path,
        agent: str = DEFAULT_AGENT,
        model: str = DEFAULT_MODEL,
        output: dict[str, Any] | None = None,
) -> StepResult:
    with AgentContext(
            usage_logging=DEFAULT_USAGE_LOGGING,
            cwd=cwd,
            inactivity_timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    ) as ctx:
        return ctx.run_agent(
            agent=agent,
            model=model,
            prompt=prompt,
            output={} if output is None else output,
        )
