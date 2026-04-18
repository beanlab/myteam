from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any

import yaml

from .agent_registry import get_agent_config
from .models import RunContext, StepDefinition, StepResult
from .reference_resolver import resolve_references
from .tty_wrapper import run_pty_session

_COMPLETION_STATUS = "OBJECTIVE_COMPLETE"
_OUTPUT_INSTRUCTIONS = (
    "When the objective is complete, return only a JSON object in this form:\n"
    '{"status":"OBJECTIVE_COMPLETE","content":<result>}\n'
    "For example, if the output template is:\n"
    "summary:\n"
    "  title: short title\n"
    'Then return JSON like: {"status":"OBJECTIVE_COMPLETE","content":{"summary":{"title":"How to Code"}}}\n'
    "The `content` value must match the output template that follows."
)


def _render_yaml(value: Any) -> str:
    return yaml.safe_dump(value, sort_keys=False).strip()


def _build_prompt(step: StepDefinition, resolved_input: Any) -> str:
    sections = [
        f"# Objective:\n\n{step['prompt']}",
    ]
    if "input" in step:
        sections.append(f"Input:\n{_render_yaml(resolved_input)}")
    sections.append(f"Output Instructions:\n{_OUTPUT_INSTRUCTIONS}")
    sections.append(f"Output Template:\n{_render_yaml(step['output'])}")
    return "\n\n".join(sections) + "\n"


def _extract_completion_payload(transcript: str) -> tuple[bool, Any | None]:
    if _COMPLETION_STATUS not in transcript:
        return False, None

    decoder = json.JSONDecoder()
    for start in (index for index, char in enumerate(transcript) if char == "{"):
        candidate = transcript[start:].strip()
        try:
            parsed, end_index = decoder.raw_decode(candidate)
        except JSONDecodeError:
            continue

        if candidate[end_index:].strip():
            continue
        if (
            isinstance(parsed, dict)
            and parsed.get("status") == _COMPLETION_STATUS
            and "content" in parsed
            and len(parsed) == 2
        ):
            return True, parsed["content"]

    return False, None


def _validate_output(template: dict[str, Any], value: Any) -> None:
    if not isinstance(value, dict):
        raise ValueError("Step output must be a mapping.")

    for key, nested_template in template.items():
        if key not in value:
            raise ValueError(f"Step output is missing required key: {key}")
        if isinstance(nested_template, dict):
            _validate_output(nested_template, value[key])


def execute_step(step_name: str, step: StepDefinition, run_context: RunContext) -> StepResult:
    try:
        resolved_input = (
            resolve_references(step["input"], run_context.prior_steps)
            if "input" in step
            else None
        )
    except Exception as exc:
        return StepResult(
            step_name=step_name,
            status="failed",
            error_type="reference_resolution_error",
            error_message=str(exc),
        )

    agent_name = step.get("agent", run_context.default_agent)
    try:
        agent_config = get_agent_config(agent_name)
    except Exception as exc:
        return StepResult(
            step_name=step_name,
            status="failed",
            input=resolved_input,
            agent=agent_name,
            error_type="step_execution_error",
            error_message=str(exc),
        )

    prompt = _build_prompt(step, resolved_input)

    accepted_output: Any | None = None
    completion_seen = False
    completion_transcript_chunks: list[bytes] = []

    def on_output(chunk: bytes) -> str | None:
        nonlocal accepted_output, completion_seen
        completion_transcript_chunks.append(chunk)
        transcript = b"".join(completion_transcript_chunks).decode("utf-8", errors="replace")
        completion_seen, parsed_output = _extract_completion_payload(transcript)
        if completion_seen and accepted_output is None:
            accepted_output = parsed_output
            return agent_config["exit_text"]
        return None

    try:
        pty_result = run_pty_session(
            agent_config["argv"],
            prompt,
            on_output,
        )
    except Exception as exc:
        return StepResult(
            step_name=step_name,
            status="failed",
            input=resolved_input,
            agent=agent_name,
            error_type="step_execution_error",
            error_message=str(exc),
        )

    if accepted_output is None:
        error_message = "Step exited before producing valid completion JSON."
        if completion_seen:
            error_message = "Step produced completion output that did not match the required JSON shape."
        return StepResult(
            step_name=step_name,
            status="failed",
            input=resolved_input,
            agent=agent_name,
            error_type="step_execution_error",
            error_message=error_message,
            transcript=pty_result.transcript,
        )

    try:
        _validate_output(step["output"], accepted_output)
    except ValueError as exc:
        return StepResult(
            step_name=step_name,
            status="failed",
            input=resolved_input,
            agent=agent_name,
            error_type="step_execution_error",
            error_message=str(exc),
            transcript=pty_result.transcript,
        )

    return StepResult(
        step_name=step_name,
        status="completed",
        input=resolved_input,
        agent=agent_name,
        output=accepted_output,
        transcript=pty_result.transcript,
    )
