from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict

import yaml

from .agents import DEFAULT_AGENT
from .models import CompletedStepState, StepDefinition, StepResult, WorkflowDefinition, WorkflowOutput, WorkflowRunResult
from .steps import execute_step


def run_workflow(
    workflow: WorkflowDefinition,
    *,
    default_agent: str = DEFAULT_AGENT,
    inactivity_timeout_seconds: int = 300,
    graceful_shutdown_timeout_seconds: int = 30,
    logger: Callable[[str], None] | None = None,
) -> WorkflowRunResult:
    """
    Execute a workflow in authored order and stop at the first failing step.

    Pseudocode:
    1. Start with an empty completed-step output mapping.
    2. For each authored step, execute it with the accumulated prior step state.
    3. If a step fails, stop immediately and report the failing step name.
    4. If a step succeeds, store its completed step state under the authored step name.
    5. After all steps succeed, return the final workflow output mapping.
    """
    completed_steps: WorkflowOutput = {}

    for step_name, step_definition in workflow.items():
        if logger is not None:
            logger(f"Starting step '{step_name}'")
        step_result = execute_step(
            step_name,
            step_definition,
            prior_steps=completed_steps,
            default_agent=default_agent,
            inactivity_timeout_seconds=inactivity_timeout_seconds,
            graceful_shutdown_timeout_seconds=graceful_shutdown_timeout_seconds,
        )
        if step_result.status != "completed":
            if logger is not None:
                if step_result.error_message:
                    logger(f"Step '{step_name}' failed: {step_result.error_message}")
                else:
                    logger(f"Step '{step_name}' failed.")
            return WorkflowRunResult(
                status="failed",
                output=completed_steps or None,
                failed_step_name=step_name,
                error_message=step_result.error_message,
            )

        completed_steps[step_name] = _build_completed_step_state(
            step_definition=step_definition,
            step_result=step_result,
        )
        if logger is not None:
            logger(f"Completed step '{step_name}'")
            logger(yaml.safe_dump(asdict(step_result), sort_keys=True).rstrip())

    return WorkflowRunResult(status="completed", output=completed_steps)


def _build_completed_step_state(
    *,
    step_definition: StepDefinition,
    step_result: StepResult,
) -> CompletedStepState:
    """
    Build the stored step state exposed to later workflow references.

    Pseudocode:
    1. Preserve the authored prompt.
    2. Require the executor to provide the resolved agent name for a completed step.
    3. Require the executor to provide resolved input when the step authored input.
    4. Store the completed step output payload.
    """
    if not step_result.agent_name:
        raise ValueError(f"Completed step '{step_result.step_name}' is missing agent_name.")

    completed_state: CompletedStepState = {
        "prompt": step_definition["prompt"],
        "input": step_result.resolved_input,
        "agent": step_result.agent_name,
        "output": step_result.output,
    }
    return completed_state
