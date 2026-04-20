from __future__ import annotations

from .agent_registry import DEFAULT_AGENT
from .models import RunContext, WorkflowDefinition, WorkflowOutput, WorkflowRunResult
from .step_executor import execute_step


def run_workflow(
    workflow: WorkflowDefinition,
    *,
    default_agent: str = DEFAULT_AGENT,
) -> WorkflowRunResult:
    completed_steps: WorkflowOutput = {}

    for step_name, step in workflow.items():
        result = execute_step(
            step_name,
            step,
            RunContext(prior_steps=completed_steps, default_agent=default_agent),
        )
        if result.status != "completed":
            return WorkflowRunResult(
                status="failed",
                output=completed_steps,
                failed_step_name=step_name,
                error_type=result.error_type,
                error_message=result.error_message,
            )

        completed_steps[step_name] = {
            "prompt": step["prompt"],
            "input": result.input,
            "agent": result.agent,
            "output": result.output,
        }

    return WorkflowRunResult(status="completed", output=completed_steps)
