from __future__ import annotations

import json
import os
from pathlib import Path
import uuid
from typing import Any

from myteam.disclosure import PROJECT_ROOT_ENV_VAR

from .agents import resolve_agent_runtime_config
from .agents.runtime import AgentRuntimeConfig, AgentSessionContext
from .models import StepResult
from .terminal.session import run_terminal_session


def run_agent(
    *,
    prompt: str,
    output: dict[str, Any],
    input: Any = None,
    agent: str | None = None,
    model: str | None = None,
    interactive: bool = True,
    resume_session_id: str | None = None,
    fork_session_id: str | None = None,
    extra_args: list[str] | None = None,
    cwd: Path | str | None = None,
) -> StepResult:
    """
    Execute one workflow step with an interactive agent runtime.

    Args:
        prompt: Objective text the agent should complete.
        output: Expected structured result shape the agent must report.
        input: Optional resolved input data included in the step prompt.
        agent: Workflow agent runtime name to launch.
        model: Optional model name appended to the agent argv as ``--model <model>``.
        interactive: Whether to launch the agent in interactive mode.
        resume_session_id: Optional existing agent session to resume.
        fork_session_id: Optional existing agent session to fork into a new session.
        extra_args: Optional additional argv items appended after any model argument.
        cwd: Optional working directory for launching the agent process.
    """
    transcript = ""
    try:
        resolved_input = input
        _validate_session_arguments(
            interactive=interactive,
            resume_session_id=resume_session_id,
            fork_session_id=fork_session_id,
        )
        agent_name = _require_agent_name(agent)
        project_root = _resolve_project_root()
        launch_cwd = project_root if cwd is None else Path(cwd).resolve()
        session_context = AgentSessionContext(
            home=Path.home().resolve(),
            project_root=project_root,
            launch_cwd=launch_cwd,
        )
        agent_config = _resolve_agent_config(agent_name, session_context=session_context)
        nonce = str(uuid.uuid4())
        prompt_text = _build_step_prompt(
            resolved_input=resolved_input,
            objective_text=prompt,
            output_template=output,
            session_nonce=nonce,
        )
        argv = _build_agent_argv(
            agent_config=agent_config,
            prompt_text=prompt_text,
            interactive=interactive,
            resume_session_id=resume_session_id,
            fork_session_id=fork_session_id,
            model=model,
            extra_args=extra_args,
        )
        session_result = run_terminal_session(
            argv,
            exit_input=agent_config.exit_sequence,
            cwd=launch_cwd,
            inactivity_timeout_seconds=300,
        )
        transcript = session_result.transcript
        if session_result.payload is None:
            raise StepExecutionError(
                "completion_missing",
                "Workflow agent exited before reporting a structured result.",
            )
        _validate_step_output(output, session_result.payload)
        discovered_session_id = _resolve_session_id(
            payload=session_result.payload,
            resume_session_id=resume_session_id,
            nonce=nonce,
            agent_config=agent_config,
        )
        return StepResult(
            status="completed",
            output=session_result.payload,
            resolved_input=resolved_input,
            agent_name=agent_name,
            transcript=transcript,
            exit_code=session_result.exit_code,
            session_id=discovered_session_id,
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


def _resolve_project_root() -> Path:
    configured_agent_root = os.environ.get(PROJECT_ROOT_ENV_VAR)
    if configured_agent_root:
        return Path(configured_agent_root).resolve().parent

    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / ".myteam").is_dir():
            return candidate
    return cwd


def _resolve_agent_config(agent_name: str, *, session_context: AgentSessionContext) -> AgentRuntimeConfig:
    try:
        return resolve_agent_runtime_config(
            agent_name,
            project_root=session_context.project_root,
            session_context=session_context,
        )
    except KeyError as exc:
        raise StepExecutionError("agent_resolution", str(exc)) from exc


def _validate_session_arguments(
    *,
    interactive: bool,
    resume_session_id: str | None,
    fork_session_id: str | None,
) -> None:
    if not isinstance(interactive, bool):
        raise StepExecutionError(
            "argument_validation",
            "Step field 'interactive' must be a boolean when provided.",
        )
    if resume_session_id is not None and fork_session_id is not None:
        raise StepExecutionError(
            "argument_validation",
            "Step fields 'resume_session_id' and 'fork_session_id' are mutually exclusive.",
        )
    if resume_session_id is not None and (not isinstance(resume_session_id, str) or not resume_session_id):
        raise StepExecutionError(
            "argument_validation",
            "Step field 'resume_session_id' must be a non-empty string when provided.",
        )
    if fork_session_id is not None and (not isinstance(fork_session_id, str) or not fork_session_id):
        raise StepExecutionError(
            "argument_validation",
            "Step field 'fork_session_id' must be a non-empty string when provided.",
        )


def _build_agent_argv(
    *,
    agent_config: AgentRuntimeConfig,
    prompt_text: str,
    interactive: bool,
    resume_session_id: str | None,
    fork_session_id: str | None,
    model: str | None,
    extra_args: list[str] | None,
) -> list[str]:
    try:
        argv = agent_config.build_argv(prompt_text, interactive, resume_session_id, fork_session_id)
    except Exception as exc:
        raise StepExecutionError(
            "agent_argv",
            f"Failed to build argv for workflow agent '{agent_config.name}': {exc}",
        ) from exc

    if not isinstance(argv, list) or any(not isinstance(item, str) for item in argv):
        raise StepExecutionError(
            "agent_argv",
            f"Workflow agent '{agent_config.name}' build_argv must return a list of strings.",
        )

    if model is not None:
        if not isinstance(model, str) or not model:
            raise StepExecutionError(
                "argument_validation",
                "Step field 'model' must be a non-empty string when provided.",
            )
        argv.extend(["--model", model])

    if extra_args is not None:
        if not isinstance(extra_args, list):
            raise StepExecutionError(
                "argument_validation",
                "Step field 'extra_args' must be a list of strings when provided.",
            )
        for index, arg in enumerate(extra_args):
            if not isinstance(arg, str):
                raise StepExecutionError(
                    "argument_validation",
                    f"Step field 'extra_args[{index}]' must be a string.",
                )
            argv.append(arg)

    return argv


def _build_step_prompt(
    *,
    resolved_input: Any,
    objective_text: str,
    output_template: dict[str, Any],
    session_nonce: str | None,
) -> str:
    sections = [
        "Complete the objective below.",
        "",
        "Return the final workflow result by calling this command:",
        "Replace the placeholder values below with the real final result content.",
        "",
        "myteam workflow-result <<'JSON'",
        json.dumps(output_template, indent=2),
        "JSON",
        "",
        "Do not print result markers in the terminal.",
    ]
    if session_nonce is not None:
        sections.append(f"Session nonce: {session_nonce}")
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


def _resolve_session_id(
    *,
    payload: Any,
    resume_session_id: str | None,
    nonce: str | None,
    agent_config: AgentRuntimeConfig,
) -> str | None:
    payload_session_id = _extract_session_id(payload)
    if payload_session_id is not None:
        return payload_session_id
    if resume_session_id is not None:
        return resume_session_id
    if nonce is None:
        return None
    try:
        return agent_config.get_session_id(nonce)
    except LookupError as exc:
        raise StepExecutionError("session_discovery", str(exc)) from exc


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
