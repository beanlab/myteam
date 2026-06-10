"""Workflow/session result models and result reporting."""
from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any


@dataclass
class UsageInfo:
    model: str = ""
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0

    def add(self, usage: "UsageInfo") -> None:
        self.input_tokens += usage.input_tokens
        self.cached_input_tokens += usage.cached_input_tokens
        self.output_tokens += usage.output_tokens
        self.reasoning_output_tokens += usage.reasoning_output_tokens
        self.total_tokens += usage.total_tokens
        self.estimated_cost += usage.estimated_cost


@dataclass
class SessionResult:
    output: dict[str, Any]
    usage: list[UsageInfo]
    transcript: str
    session_id: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "output": self.output,
            "usage": [asdict(item) for item in self.usage],
            "transcript": self.transcript,
            "session_id": self.session_id,
        }


def report_result(result_json=None, status: str = "ok") -> None:
    """Report a JSON-compatible result to the active mothership."""
    from ..proto import report_result as proto_report_result

    proto_report_result(_jsonable(result_json), status=status)


def _jsonable(value: Any) -> Any:
    if isinstance(value, SessionResult):
        return value.output
    if is_dataclass(value):
        return asdict(value)
    return value
