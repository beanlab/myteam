from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

from ..agents import get_agent_config


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
