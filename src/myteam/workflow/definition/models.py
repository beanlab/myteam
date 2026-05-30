from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional, TypedDict

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, RootModel, field_validator, model_validator


class AgentConfig(TypedDict):
    name: str
    argv: list[str]


class StepDefinition(TypedDict, total=False):
    prompt: str
    output: dict[str, Any]
    input: Any
    agent: str
    model: str
    extra_args: tuple[str, ...]
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


class ProjectWorkflowDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    agent: Optional[str] = Field(default=None, min_length=1)
    model: Optional[str] = Field(default=None, min_length=1)
    interactive: Optional[bool] = None
    session_id: Optional[str] = Field(default=None, min_length=1)
    fork: Optional[bool] = Field(default=None)
    extra_args: Optional[tuple[str, ...]] = Field(default=None)
    usage_logging: Optional[Literal["none", "summary", "per_model", "verbose"]] = Field(default=None)
    timeout: Optional[PositiveInt] = Field(default=None)

    @field_validator("extra_args", mode="before")
    @classmethod
    def _coerce_extra_args(cls, value: Any) -> tuple[str, ...] | None:
        if value is None:
            return None
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(value)
        return value


class StepDefinitionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    prompt: str = Field(min_length=1)
    output: dict[str, Any] = Field(default_factory=dict)
    input: Any = None
    agent: Optional[str] = Field(default=None, min_length=1)
    model: Optional[str] = Field(default=None, min_length=1)
    extra_args: tuple[str, ...] | None = None
    interactive: bool | None = None
    session_id: Optional[str] = Field(default=None, min_length=1)
    fork: bool | None = None

    @field_validator("extra_args", mode="before")
    @classmethod
    def _coerce_extra_args(cls, value: Any) -> tuple[str, ...] | None:
        if value is None:
            return None
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(value)
        return value

    @model_validator(mode="after")
    def _fork_requires_session(self) -> "StepDefinitionModel":
        if self.fork and self.session_id is None:
            raise ValueError("field 'session_id' is required when 'fork' is true.")
        return self

    @model_validator(mode="after")
    def _agent_must_exist(self) -> "StepDefinitionModel":
        if self.agent is not None:
            from ..agents import get_agent_config

            try:
                get_agent_config(self.agent)
            except KeyError as exc:
                raise ValueError(str(exc)) from exc
        return self


class WorkflowDefinitionModel(RootModel[dict[str, StepDefinitionModel]]):
    model_config = ConfigDict(strict=True)


class StepExecutionArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    input: Any = None
    agent: str = Field(min_length=1)
    interactive: bool = True
    session_id: Optional[str] = Field(default=None, min_length=1)
    fork: bool = False
    extra_args: tuple[str, ...] | None = None
    model: Optional[str] = Field(default=None, min_length=1)

    @field_validator("extra_args", mode="before")
    @classmethod
    def _coerce_extra_args(cls, value: Any) -> tuple[str, ...] | None:
        if value is None:
            return None
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(value)
        return value

    @model_validator(mode="after")
    def validate_fork_requires_session(self) -> "StepExecutionArgs":
        if self.fork and self.session_id is None:
            raise ValueError("session_id is required when fork is true")
        return self


@dataclass
class RunState:
    transcript: str = ""
    usage: UsageInfo | None = None
    usage_state: str = "not_attempted"
    usage_error_message: str | None = None
    session_path: "Path | None" = None
    nonce: str | None = None
    agent_config: "AgentRuntimeConfig | None" = None


@dataclass(frozen=True)
class PreparedStep:
    nonce: str
    agent_config: "AgentRuntimeConfig"
    prompt_text: str
    objective_text: str
    argv: list[str]
    resolved_input: Any
    output_template: dict[str, Any]
    agent_name: str | None
    model: str | None
    interactive: bool
    session_id: str | None
    fork: bool
    extra_args: tuple[str, ...] | None
    skills: tuple[tuple[str, str], ...] | None
    tasks: tuple[tuple[str, str], ...] | None


@dataclass
class UsageInfo:
    model: str = ""
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0

    def add(self, usage: UsageInfo) -> None:
        self.input_tokens += usage.input_tokens
        self.cached_input_tokens += usage.cached_input_tokens
        self.output_tokens += usage.output_tokens
        self.reasoning_output_tokens += usage.reasoning_output_tokens
        self.total_tokens += usage.total_tokens
        self.estimated_cost += usage.estimated_cost


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
    - ``unexpected_error``: the executor raised an uncategorized internal exception.

    Usage tracking values:
    - ``not_attempted``: usage lookup was skipped because the step failed before launch.
    - ``collected``: usage lookup succeeded and ``usage`` is populated.
    - ``unavailable``: usage lookup was attempted, but the runtime could not provide usage data.
    - ``no_get_usage_info_implemented``: the agent config does not define ``get_usage_info``.
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
    usage: UsageInfo | None = None
    usage_state: str = "not_attempted"
    usage_error_message: str | None = None


@dataclass
class WorkflowRunResult:
    status: str
    output: WorkflowOutput | None = None
    failed_step_name: str | None = None
    error_message: str | None = None
