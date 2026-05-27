from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StepExecutionArgs(BaseModel):
    input: Any = None
    agent_name: str = Field(min_length=1)
    interactive: bool = True
    session_id: str | None = Field(default=None, min_length=1)
    fork: bool = False
    extra_args: list[str] | None = None
    model: str | None = Field(default=None, min_length=1)

    model_config = ConfigDict(extra="forbid", strict=True)

    @model_validator(mode="after")
    def validate_fork_requires_session(self) -> "StepExecutionArgs":
        if self.fork and self.session_id is None:
            raise ValueError("session_id is required when fork is true")
        return self
