from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import yaml

from .agent_registry import DEFAULT_AGENT, get_agent_config
from .models import AgentConfig, PtyRunResult, StepDefinition, StepResult, WorkflowOutput
from .reference_resolver import resolve_references
from .tty_wrapper import run_pty_session


def execute_step(
    step_name: str,
    step_definition: StepDefinition,
    *,
    prior_steps: WorkflowOutput,
    default_agent: str = DEFAULT_AGENT,
    inactivity_timeout_seconds: int = 300,
    graceful_shutdown_timeout_seconds: int = 30,
) -> StepResult:
    """Execute one workflow step against the configured interactive agent."""
    watcher = CompletionWatcher()
    transcript = ""
    try:
        resolved_input = _resolve_step_input(step_definition, prior_steps)
        agent_name = _resolve_agent_name(step_definition, default_agent)
        agent_config = _resolve_agent_config(agent_name)
        prompt_text = _build_step_prompt(
            resolved_input=resolved_input,
            objective_text=step_definition["prompt"],
            output_template=step_definition["output"],
        )
        pty_result = _run_step_session(
            prompt_text=prompt_text,
            agent_config=agent_config,
            watcher=watcher,
            inactivity_timeout_seconds=inactivity_timeout_seconds,
            graceful_shutdown_timeout_seconds=graceful_shutdown_timeout_seconds,
        )
        transcript = pty_result.transcript
        accepted_content = _extract_completed_content(watcher, pty_result)
        _ensure_clean_session_exit(pty_result)
        _validate_step_output(step_definition["output"], accepted_content)
        return _build_completed_step_result(
            step_name=step_name,
            transcript=transcript,
            output=accepted_content,
            resolved_input=resolved_input,
            agent_name=agent_name,
        )
    except StepExecutionError as exc:
        transcript = transcript or watcher.transcript
        return _build_failed_step_result(
            step_name=step_name,
            transcript=transcript,
            error_type=exc.error_type,
            error_message=exc.error_message,
        )


def _resolve_step_input(step_definition: StepDefinition, prior_steps: WorkflowOutput) -> Any:
    """
    Pseudocode:
    1. If the step has no authored input, return None.
    2. Resolve any `$step.path` references against prior completed step state.
    3. Convert reference-resolution failures into step execution failures.
    """
    if "input" not in step_definition:
        return None
    try:
        return resolve_references(step_definition["input"], prior_steps)
    except ValueError as exc:
        raise StepExecutionError("reference_resolution", str(exc)) from exc


def _resolve_agent_name(step_definition: StepDefinition, default_agent: str) -> str:
    """
    Pseudocode:
    1. Use the authored `agent` when present.
    2. Otherwise use the workflow runtime default agent.
    """
    return step_definition.get("agent", default_agent)


def _resolve_agent_config(agent_name: str) -> AgentConfig:
    """
    Pseudocode:
    1. Look up the configured agent in the workflow agent registry.
    2. Convert registry lookup failures into executor step failures.
    """
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
    """
    Pseudocode:
    1. Start with the fixed completion contract instructions.
    2. Include the resolved input as YAML when input exists.
    3. Include the authored objective text.
    4. Include the authored output template as YAML.
    5. End with a reminder to return only the completion JSON object.
    """
    sections = [
        "Complete the objective below.",
        "When you are done, return exactly one JSON object with this shape:",
        '{"status": "OBJECTIVE_COMPLETE", "content": <result>}',
    ]
    if resolved_input is not None:
        sections.extend(
            [
                "",
                "Input:",
                _dump_yaml_block(resolved_input),
            ]
        )
    sections.extend(
        [
            "",
            "Objective:",
            objective_text,
            "",
            "Output template:",
            _dump_yaml_block(output_template),
            "",
            "Return only the completion JSON object when the objective is complete.",
        ]
    )
    return "\n".join(sections)


def _run_step_session(
    *,
    prompt_text: str,
    agent_config: AgentConfig,
    watcher: "CompletionWatcher",
    inactivity_timeout_seconds: int,
    graceful_shutdown_timeout_seconds: int,
) -> PtyRunResult:
    """
    Pseudocode:
    1. Start the configured PTY-backed agent session.
    2. Send the canonical step prompt as the initial input.
    3. Feed streamed output chunks into the completion watcher.
    4. Translate timeout and launch failures into executor-specific errors.
    """
    try:
        return run_pty_session(
            agent_config["argv"],
            prompt_text,
            lambda chunk: _handle_output_chunk(chunk, watcher, agent_config),
            inactivity_timeout_seconds=inactivity_timeout_seconds,
            graceful_shutdown_timeout_seconds=graceful_shutdown_timeout_seconds,
        )
    except TimeoutError as exc:
        raise StepExecutionError("timeout", str(exc)) from exc
    except OSError as exc:
        raise StepExecutionError("agent_launch", f"Failed to launch workflow agent: {exc}") from exc


def _handle_output_chunk(
    chunk: bytes,
    watcher: "CompletionWatcher",
    agent_config: AgentConfig,
) -> str | None:
    """
    Pseudocode:
    1. Append the chunk to the completion watcher.
    2. If the watcher has accepted a completion payload, return the agent exit text.
    3. Otherwise return None so the PTY session continues normally.
    """
    watcher.append(chunk)
    if watcher.completed:
        return agent_config["exit_text"]
    return None


def _extract_completed_content(watcher: "CompletionWatcher", pty_result: PtyRunResult) -> Any:
    """
    Pseudocode:
    1. If the watcher accepted a completion payload, return its content.
    2. If the transcript mentioned `OBJECTIVE_COMPLETE` but no valid payload was parsed, fail as malformed completion.
    3. Otherwise fail because the session ended before a valid completion was produced.
    """
    if watcher.completed:
        return watcher.content

    if "OBJECTIVE_COMPLETE" in pty_result.transcript:
        raise StepExecutionError(
            "completion_invalid",
            "Workflow agent emitted OBJECTIVE_COMPLETE but did not produce a valid completion JSON object.",
        )

    raise StepExecutionError(
        "completion_missing",
        "Workflow agent exited before producing a valid completion JSON object.",
    )


def _ensure_clean_session_exit(pty_result: PtyRunResult) -> None:
    """
    Pseudocode:
    1. Accept a normal zero exit code.
    2. Otherwise fail because the child process exited unsuccessfully.
    """
    if pty_result.exit_code == 0:
        return
    raise StepExecutionError(
        "agent_failure_after_output",
        f"Workflow agent exited with status {pty_result.exit_code}.",
    )


def _validate_step_output(output_template: dict[str, Any], output_value: Any) -> None:
    """
    Pseudocode:
    1. Walk the authored output template recursively.
    2. Whenever the template node is a mapping, require a mapping value at runtime.
    3. Require every template key to exist in the runtime value.
    4. Ignore scalar leaf template values; they are descriptive only.
    """
    try:
        _validate_output_node(output_template, output_value, path="output")
    except ValueError as exc:
        raise StepExecutionError("output_validation", str(exc)) from exc


def _build_completed_step_result(
    *,
    step_name: str,
    transcript: str,
    output: Any,
    resolved_input: Any,
    agent_name: str,
) -> StepResult:
    return StepResult(
        step_name=step_name,
        status="completed",
        output=output,
        resolved_input=resolved_input,
        agent_name=agent_name,
        transcript=transcript,
    )


def _build_failed_step_result(
    *,
    step_name: str,
    transcript: str,
    error_type: str,
    error_message: str,
) -> StepResult:
    return StepResult(
        step_name=step_name,
        status="failed",
        error_type=error_type,
        error_message=error_message,
        transcript=transcript,
    )


def _dump_yaml_block(value: Any) -> str:
    rendered = yaml.safe_dump(value, sort_keys=False, allow_unicode=False).rstrip()
    return rendered if rendered else "null"


def _validate_output_node(template_node: Any, output_node: Any, *, path: str) -> None:
    if not isinstance(template_node, dict):
        return
    if not isinstance(output_node, dict):
        raise ValueError(f"{path} must be a mapping.")

    for key, nested_template in template_node.items():
        if key not in output_node:
            raise ValueError(f"{path} is missing required key: {key}")
        _validate_output_node(nested_template, output_node[key], path=f"{path}.{key}")


@dataclass
class StepExecutionError(Exception):
    error_type: str
    error_message: str


@dataclass
class CompletionWatcher:
    """Accumulate PTY output and detect the first accepted completion object."""

    _transcript_parts: list[str] = field(default_factory=list)
    _accepted_payload: dict[str, Any] | None = None

    def append(self, chunk: bytes) -> None:
        text = chunk.decode("utf-8", errors="replace")
        self._transcript_parts.append(text)
        if self._accepted_payload is None:
            self._try_accept_completion()

    @property
    def transcript(self) -> str:
        return "".join(self._transcript_parts)

    @property
    def completed(self) -> bool:
        return self._accepted_payload is not None

    @property
    def completion_payload(self) -> dict[str, Any] | None:
        return self._accepted_payload

    @property
    def content(self) -> Any | None:
        if self._accepted_payload is None:
            return None
        return self._accepted_payload["content"]

    def _try_accept_completion(self) -> None:
        """
        Pseudocode:
        1. Skip parsing work until the transcript contains `OBJECTIVE_COMPLETE`.
        2. Anchor on the most recent completion marker in the transcript.
        3. Find the nearest plausible opening `{` before that marker and try to close one object.
        4. If the object is incomplete, defer until more output arrives.
        5. If the object is complete, parse it, including a normalized retry for line-wrapped TTY output.
        6. Accept the first parsed payload with the exact required top-level completion shape.
        """
        if "OBJECTIVE_COMPLETE" not in self.transcript:
            return

        candidate_text = self._candidate_json_text()
        if candidate_text is None:
            return

        payload = self._parse_candidate_payload(candidate_text)
        if self._is_completion_payload(payload):
            self._accepted_payload = payload

    def _candidate_json_text(self) -> str | None:
        """
        Pseudocode:
        1. Find the most recent `OBJECTIVE_COMPLETE` marker in the transcript.
        2. Walk backward to the nearest `{` before that marker and treat it as the start.
        3. From that start, scan forward with JSON string/escape tracking until brace depth returns to zero.
        4. Return the candidate object text when complete, or None if more output is needed.
        """
        transcript = self.transcript
        marker_index = transcript.rfind("OBJECTIVE_COMPLETE")
        if marker_index < 0:
            return None

        start_index = transcript.rfind("{", 0, marker_index + 1)
        if start_index < 0:
            return None

        depth = 0
        in_string = False
        escaping = False

        for index in range(start_index, len(transcript)):
            char = transcript[index]

            if index == start_index:
                depth = 1
                continue

            if escaping:
                escaping = False
                continue

            if char == "\\" and in_string:
                escaping = True
                continue

            if char == '"':
                in_string = not in_string
                continue

            if in_string:
                continue

            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return transcript[start_index:index + 1]

        return None

    def _parse_candidate_payload(self, candidate_text: str) -> dict[str, Any] | None:
        for text in (candidate_text, self._normalize_wrapped_json(candidate_text)):
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        return None

    def _normalize_wrapped_json(self, candidate_text: str) -> str:
        """
        Pseudocode:
        1. Walk the candidate JSON text while tracking JSON string/escape state.
        2. Preserve all characters except raw carriage returns.
        3. Drop raw newlines that appear inside JSON strings, since they are invalid JSON and
           commonly come from terminal-wrapped output rather than intentional content.
        """
        # This is intentionally a lossy recovery path for PTY output. A literal raw newline
        # inside a JSON string is invalid JSON; valid multiline content should be emitted as
        # an escaped ``\\n`` sequence. In practice, interactive terminal sessions can inject
        # display-wrapping newlines into otherwise valid JSON text, so we strip only raw
        # in-string newlines here to recover the intended payload while preserving escaped
        # newlines and all structure outside strings.
        output_chars: list[str] = []
        in_string = False
        escaping = False

        for char in candidate_text:
            if escaping:
                output_chars.append(char)
                escaping = False
                continue

            if char == "\r":
                continue

            if char == "\\" and in_string:
                output_chars.append(char)
                escaping = True
                continue

            if char == '"':
                output_chars.append(char)
                in_string = not in_string
                continue

            if char == "\n" and in_string:
                continue

            output_chars.append(char)

        return "".join(output_chars)

    def _is_completion_payload(self, payload: dict[str, Any] | None) -> bool:
        if payload is None:
            return False
        if set(payload) != {"status", "content"}:
            return False
        if payload.get("status") != "OBJECTIVE_COMPLETE":
            return False
        return True
