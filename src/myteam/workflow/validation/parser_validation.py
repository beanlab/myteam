from __future__ import annotations

from typing import Any, ClassVar
from typing_extensions import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, ValidationError, field_validator, model_validator

from ..agents import get_agent_config
from ..models import StepDefinition


def _format_loc(loc: tuple[Any, ...]) -> str:
    parts: list[str] = []
    for item in loc:
        if isinstance(item, int) and parts:
            parts[-1] = f"{parts[-1]}[{item}]"
        else:
            parts.append(str(item))
    return ".".join(parts)


class StepDefinitionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    _ALLOWED_KEYS: ClassVar[set[str]] = {
        "prompt",
        "output",
        "input",
        "agent",
        "model",
        "extra_args",
        "interactive",
        "session_id",
        "fork",
    }

    prompt: Annotated[StrictStr, Field(min_length=1)]
    output: Any = Field(default_factory=dict)
    input: Any = None
    agent: Annotated[StrictStr | None, Field(min_length=1)] = None
    model: Annotated[StrictStr | None, Field(min_length=1)] = None
    extra_args: list[StrictStr] | None = None
    interactive: StrictBool | None = None
    session_id: Annotated[StrictStr | None, Field(min_length=1)] = None
    fork: StrictBool | None = None

    @staticmethod
    def _validate_nested_keys(value: Any, *, context: str, lists_allowed: bool) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if not isinstance(key, str) or not key.isidentifier():
                    raise ValueError(f"{context} contains non-identifier key: {key!r}")
                if isinstance(nested, list) and not lists_allowed:
                    raise ValueError(f"{context}.{key} must not contain a list.")
                StepDefinitionModel._validate_nested_keys(
                    nested,
                    context=f"{context}.{key}",
                    lists_allowed=lists_allowed,
                )
            return
        if lists_allowed and isinstance(value, list):
            for index, nested in enumerate(value):
                StepDefinitionModel._validate_nested_keys(
                    nested,
                    context=f"{context}[{index}]",
                    lists_allowed=lists_allowed,
                )

    @field_validator("output")
    @classmethod
    def _validate_output(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            raise ValueError("must be a mapping.")
        cls._validate_nested_keys(value, context="output", lists_allowed=False)
        return value

    @field_validator("input")
    @classmethod
    def _validate_input(cls, value: Any) -> Any:
        if value is not None:
            cls._validate_nested_keys(value, context="input", lists_allowed=True)
        return value

    @model_validator(mode="after")
    def _fork_requires_session(self) -> "StepDefinitionModel":
        if self.fork and self.session_id is None:
            raise ValueError("field 'session_id' is required when 'fork' is true.")
        return self

    @classmethod
    def validate_step_definition(cls, step_name: str, definition: Any) -> StepDefinition:
        if not isinstance(definition, dict):
            raise ValueError(f"Workflow step '{step_name}' must be a mapping.")

        extra_keys = sorted(set(definition) - cls._ALLOWED_KEYS)
        if extra_keys:
            raise ValueError(f"Workflow step '{step_name}' has unsupported keys: {', '.join(extra_keys)}.")
        if "prompt" not in definition:
            raise ValueError(f"Workflow step '{step_name}' is missing required keys: prompt.")

        try:
            validated = cls.model_validate(definition)
        except ValidationError as exc:
            error = exc.errors()[0]
            field = _format_loc(tuple(error["loc"]))
            kind = error["type"]
            if field.startswith("extra_args["):
                raise ValueError(f"Workflow step '{step_name}' field '{field}' must be a string.") from exc
            if field == "output" and kind == "value_error":
                message = error["msg"]
                if message.startswith("Value error, "):
                    message = message.removeprefix("Value error, ")
                if message == "must be a mapping.":
                    raise ValueError(f"Workflow step '{step_name}' field 'output' must be a mapping.") from exc
                if message.startswith(("output.", "input.")):
                    raise ValueError(f"Workflow step '{step_name}'.{message}") from exc
                raise ValueError(f"Workflow step '{step_name}' {message}") from exc
            if kind in {"string_too_short", "string_type"}:
                raise ValueError(f"Workflow step '{step_name}' field '{field}' must be a non-empty string.") from exc
            if kind == "bool_type":
                raise ValueError(f"Workflow step '{step_name}' field '{field}' must be a boolean.") from exc
            if kind == "list_type":
                raise ValueError(f"Workflow step '{step_name}' field '{field}' must be a list of strings.") from exc
            message = error["msg"]
            if message.startswith("Value error, "):
                message = message.removeprefix("Value error, ")
            if message.startswith(("output.", "input.")):
                raise ValueError(f"Workflow step '{step_name}'.{message}") from exc
            raise ValueError(f"Workflow step '{step_name}' {message}") from exc

        if validated.agent is not None:
            try:
                get_agent_config(validated.agent)
            except KeyError as exc:
                raise ValueError(str(exc)) from exc

        result: StepDefinition = {"prompt": validated.prompt, "input": validated.input, "output": validated.output}
        if validated.agent is not None:
            result["agent"] = validated.agent
        if validated.model is not None:
            result["model"] = validated.model
        if validated.extra_args is not None:
            result["extra_args"] = validated.extra_args
        if validated.interactive is not None:
            result["interactive"] = validated.interactive
        if validated.session_id is not None:
            result["session_id"] = validated.session_id
        if validated.fork is not None:
            result["fork"] = validated.fork
        return result
