from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict


class AgentConfig(TypedDict):
    name: str
    argv: list[str]
    exit_text: str | None


class StepDefinition(TypedDict, total=False):
    prompt: str
    output: dict[str, Any]
    input: Any
    agent: str


WorkflowDefinition = dict[str, StepDefinition]


class CompletedStepState(TypedDict, total=False):
    prompt: str
    input: Any
    agent: str | None
    output: Any


WorkflowOutput = dict[str, CompletedStepState]


@dataclass
class RunContext:
    prior_steps: dict[str, Any]
    default_agent: str


@dataclass
class StepResult:
    step_name: str
    status: str
    input: Any | None = None
    agent: str | None = None
    output: Any | None = None
    error_type: str | None = None
    error_message: str | None = None
    transcript: str = ""


@dataclass
class WorkflowRunResult:
    status: str
    output: WorkflowOutput | None = None
    failed_step_name: str | None = None


@dataclass
class PtyRunResult:
    exit_code: int
    transcript: str = ""
