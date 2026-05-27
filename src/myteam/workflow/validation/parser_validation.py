from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

from ..agents import get_agent_config


def _validate_nested_keys(value: Any, *, context: str, lists_allowed: bool) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str) or not key.isidentifier():
                raise ValueError(f"{context} contains non-identifier key: {key!r}")
            if isinstance(nested, list) and not lists_allowed:
                raise ValueError(f"{context}.{key} must not contain a list.")
            _validate_nested_keys(nested, context=f"{context}.{key}", lists_allowed=lists_allowed)
        return
    if lists_allowed and isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_nested_keys(nested, context=f"{context}[{index}]", lists_allowed=lists_allowed)


class StepDefinitionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    prompt: str = Field(min_length=1)
    output: dict[str, Any] = Field(default_factory=dict)
    input: Any = None
    agent: Optional[str] = Field(default=None, min_length=1)
    model: Optional[str] = Field(default=None, min_length=1)
    extra_args: list[str] | None = None
    interactive: bool | None = None
    session_id: Optional[str] = Field(default=None, min_length=1)
    fork: bool | None = None

    @field_validator("output")
    @classmethod
    def _validate_output(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_nested_keys(value, context="output", lists_allowed=False)
        return value

    @field_validator("input")
    @classmethod
    def _validate_input(cls, value: Any) -> Any:
        _validate_nested_keys(value, context="input", lists_allowed=True)
        return value

    @model_validator(mode="after")
    def _fork_requires_session(self) -> "StepDefinitionModel":
        if self.fork and self.session_id is None:
            raise ValueError("field 'session_id' is required when 'fork' is true.")
        return self

    @model_validator(mode="after")
    def _agent_must_exist(self) -> "StepDefinitionModel":
        if self.agent is not None:
            try:
                get_agent_config(self.agent)
            except KeyError as exc:
                raise ValueError(str(exc)) from exc
        return self


class WorkflowDefinitionModel(RootModel[dict[str, StepDefinitionModel]]):
    model_config = ConfigDict(strict=True)

    @model_validator(mode="after")
    def _validate_step_names(self) -> "WorkflowDefinitionModel":
        invalid_name = next((name for name in self.root if not name.isidentifier()), None)
        if invalid_name is not None:
            raise ValueError(f"Workflow step name must be an identifier: {invalid_name!r}")
        return self
