from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict


class AgentConfig(TypedDict):
    name: str
    argv: list[str]


class StepDefinition(TypedDict, total=False):
    prompt: str
    output: dict[str, Any]
    input: Any
    agent: str
    model: str
    extra_args: list[str]
    interactive: bool
    session_id: str
    fork: bool


WorkflowDefinition = dict[str, StepDefinition]


class CompletedStepState(TypedDict, total=False):
    prompt: str
    input: Any
    agent: str
    output: Any


WorkflowOutput = dict[str, CompletedStepState]


@dataclass
class StepResult:
    """
    Result of executing one workflow step.

    Status values:
    - ``completed``: the step produced a valid completion payload, the agent session
      exited cleanly, and the returned content matched the authored output template.
    - ``failed``: the step did not complete successfully.

    When ``status`` is ``failed``, ``error_type`` identifies the failure class:
    - ``reference_resolution``: the step input referenced missing or invalid prior step data.
    - ``argument_validation``: the step provided invalid executor arguments.
    - ``agent_resolution``: the executor could not resolve the configured workflow agent.
    - ``agent_argv``: the executor could not build a valid argv for the configured workflow agent.
    - ``agent_launch``: the workflow agent process could not be started.
    - ``timeout``: the PTY session became inactive before the step completed.
    - ``completion_missing``: the agent session ended without producing a structured result.
    - ``output_validation``: the completion payload content did not satisfy the authored output template.
    - ``session_discovery``: the step completed but the runtime could not discover the new agent session id.
    """
    status: str
    output: Any | None = None
    resolved_input: Any | None = None
    agent_name: str = ""
    error_type: str | None = None
    error_message: str | None = None
    transcript: str = ""
    exit_code: int | None = None
    session_id: str | None = None


@dataclass
class WorkflowRunResult:
    status: str
    output: WorkflowOutput | None = None
    failed_step_name: str | None = None
    error_message: str | None = None
