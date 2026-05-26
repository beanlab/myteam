from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import StepResult
from .steps import AgentContext


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
