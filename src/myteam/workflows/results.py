"""Workflow/session result models and result reporting."""
from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
import json
import os
import sys
from typing import Any

from .agent_result_channel import send_agent_result
from .execution.protocol import ENV_AGENT_SESSION_RESULT_SOCKET


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
    exit_code: int
    output: dict[str, Any] | None
    usage: list[UsageInfo]
    transcript: str
    session_id: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "output": self.output,
            "usage": [asdict(item) for item in self.usage],
            "transcript": self.transcript,
            "session_id": self.session_id,
        }


def report_result(result_json: Any | None = None, status: str = "ok") -> None:
    """Report a JSON-compatible result to the active managed agent session."""

    output = _load_result(_jsonable(result_json))

    agent_result_socket = os.environ.get(ENV_AGENT_SESSION_RESULT_SOCKET)
    if not agent_result_socket:
        raise RuntimeError("No active myteam agent session is available.")

    send_agent_result(agent_result_socket, status=status, output=output)


def _jsonable(value: Any) -> Any:
    if isinstance(value, SessionResult):
        return value.output
    if is_dataclass(value):
        return asdict(value)
    return value


def _load_result(result_json: Any | None) -> Any:
    if result_json is None:
        if sys.stdin.isatty():
            return None
        text = sys.stdin.read()
    elif isinstance(result_json, str):
        text = result_json
    else:
        return result_json

    if not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text
