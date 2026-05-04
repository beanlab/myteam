from __future__ import annotations

import json
from typing import Any

from .agents import DEFAULT_AGENT, get_agent_config, get_backend
from .models import AgentConfig, StepDefinition, StepResult, WorkflowOutput
from .reference_resolver import resolve_references
from .terminal.session import run_terminal_session


def execute_step(
    step_name: str,
    step_definition: StepDefinition,
    *,
    prior_steps: WorkflowOutput,
    default_agent: str = DEFAULT_AGENT,
    inactivity_timeout_seconds: int = 300,
    graceful_shutdown_timeout_seconds: int = 30,
) -> StepResult:
    transcript = ""
    try:
        resolved_input = _resolve_step_input(step_definition, prior_steps)
        agent_name = step_definition.get("agent", default_agent)
        agent_config = _resolve_agent_config(agent_name)
        backend = get_backend(agent_config["backend"])
        prompt_text = _build_step_prompt(
            resolved_input=resolved_input,
            objective_text=step_definition["prompt"],
            output_template=step_definition["output"],
        )
        session_result = run_terminal_session(
            agent_config["argv"],
            initial_input=backend.encode_input(prompt_text),
            exit_input=backend.encode_exit(),
            inactivity_timeout_seconds=inactivity_timeout_seconds,
            graceful_shutdown_timeout_seconds=graceful_shutdown_timeout_seconds,
        )
        transcript = session_result.transcript
        if session_result.payload is None:
            raise StepExecutionError(
                "completion_missing",
                "Workflow agent exited before reporting a structured result.",
            )
        _validate_step_output(step_definition["output"], session_result.payload)
        return StepResult(
            step_name=step_name,
            status="completed",
            output=session_result.payload,
            resolved_input=resolved_input,
            agent_name=agent_name,
            transcript=transcript,
            exit_code=session_result.exit_code,
        )
    except StepExecutionError as exc:
        return StepResult(
            step_name=step_name,
            status="failed",
            error_type=exc.error_type,
            error_message=exc.error_message,
            transcript=transcript,
        )
    except TimeoutError as exc:
        return StepResult(
            step_name=step_name,
            status="failed",
            error_type="timeout",
            error_message=str(exc),
            transcript=transcript,
        )
    except OSError as exc:
        return StepResult(
            step_name=step_name,
            status="failed",
            error_type="agent_launch",
            error_message=f"Failed to launch workflow agent: {exc}",
            transcript=transcript,
        )


def _resolve_step_input(step_definition: StepDefinition, prior_steps: WorkflowOutput) -> Any:
    if "input" not in step_definition:
        return None
    try:
        return resolve_references(step_definition["input"], prior_steps)
    except ValueError as exc:
        raise StepExecutionError("reference_resolution", str(exc)) from exc


def _resolve_agent_config(agent_name: str) -> AgentConfig:
    try:
        return get_agent_config(agent_name)
    except KeyError as exc:
        raise StepExecutionError("agent_resolution", str(exc)) from exc


def _build_step_prompt(
    *,
    resolved_input: Any,
    objective_text: str,
    output_template: dict[str, Any],
) -> str:
    sections = [
        "Complete the objective below.",
        "",
        "Return the final workflow result by calling this command exactly once:",
        "",
        "myteam workflow-result <<'JSON'",
        json.dumps(output_template, indent=2),
        "JSON",
        "",
        "Do not print result markers in the terminal.",
    ]
    if resolved_input is not None:
        sections.extend(
            [
                "",
                "Input:",
                json.dumps(resolved_input, indent=2),
            ]
        )
    sections.extend(
        [
            "",
            "Objective:",
            objective_text,
        ]
    )
    return "\n".join(sections)


def _validate_step_output(output_template: dict[str, Any], output_value: Any) -> None:
    try:
        _validate_output_node(output_template, output_value, path="output")
    except ValueError as exc:
        raise StepExecutionError("output_validation", str(exc)) from exc


def _validate_output_node(template: Any, value: Any, *, path: str) -> None:
    if not isinstance(template, dict):
        return
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be a mapping.")
    for key, nested in template.items():
        if key not in value:
            raise ValueError(f"{path}.{key} is missing.")
        _validate_output_node(nested, value[key], path=f"{path}.{key}")


class StepExecutionError(Exception):
    def __init__(self, error_type: str, error_message: str) -> None:
        super().__init__(error_message)
        self.error_type = error_type
        self.error_message = error_message
