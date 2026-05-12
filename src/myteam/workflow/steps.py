from __future__ import annotations

import json
from typing import Any

from .agents import get_agent_config, get_backend
from .models import AgentConfig, StepResult
from .terminal.session import run_terminal_session


def run_agent(
    *,
    prompt: str,
    output: dict[str, Any],
    input: Any = None,
    agent: str | None = None,
    session_id: str | None = None,
) -> StepResult:
    transcript = ""
    try:
        resolved_input = input
        agent_name = _require_agent_name(agent)
        agent_config = _resolve_agent_config(agent_name)
        backend = get_backend(agent_config["backend"])
        prompt_text = _build_step_prompt(
            resolved_input=resolved_input,
            objective_text=prompt,
            output_template=output,
            session_discovery_prompt=backend.session_discovery_prompt,
        )
        session_result = run_terminal_session(
            backend.build_argv(agent_config["argv"], prompt_text, session_id=session_id),
            exit_input=backend.encode_exit(),
            inactivity_timeout_seconds=300,
        )
        transcript = session_result.transcript
        if session_result.payload is None:
            raise StepExecutionError(
                "completion_missing",
                "Workflow agent exited before reporting a structured result.",
            )
        _validate_step_output(output, session_result.payload)
        return StepResult(
            status="completed",
            output=session_result.payload,
            resolved_input=resolved_input,
            agent_name=agent_name,
            transcript=transcript,
            exit_code=session_result.exit_code,
            session_id=_extract_session_id(session_result.payload),
        )
    except StepExecutionError as exc:
        return StepResult(
            status="failed",
            error_type=exc.error_type,
            error_message=exc.error_message,
            transcript=transcript,
        )
    except TimeoutError as exc:
        return StepResult(
            status="failed",
            error_type="timeout",
            error_message=str(exc),
            transcript=transcript,
        )
    except OSError as exc:
        return StepResult(
            status="failed",
            error_type="agent_launch",
            error_message=f"Failed to launch workflow agent: {exc}",
            transcript=transcript,
        )


def _require_agent_name(agent_name: str | None) -> str:
    if not agent_name:
        raise StepExecutionError(
            "agent_resolution",
            "Step definition is missing required field 'agent'.",
        )
    return agent_name


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
    session_discovery_prompt: str,
) -> str:
    sections = [
        "Complete the objective below.",
        "",
        "Return the final workflow result by calling this command exactly once:",
        "Replace the placeholder values below with the real final result content.",
        "",
        "myteam workflow-result <<'JSON'",
        json.dumps(output_template, indent=2),
        "JSON",
        "",
        "Do not print result markers in the terminal.",
        "",
        "Session:",
        session_discovery_prompt,
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


def _extract_session_id(output_value: Any) -> str | None:
    if not isinstance(output_value, dict):
        return None
    value = output_value.get("session_id")
    if isinstance(value, str) and value:
        return value
    return None


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
