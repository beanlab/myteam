"""Internal command messages for workflow supervisor coordination."""
from __future__ import annotations

from dataclasses import dataclass
@dataclass(frozen=True)
class StartWorkflowCommand:
    request_id: str
    argv: list[str]
    parent_session_id: str | None
    cwd: str | None
    input_json: str | None


Command = StartWorkflowCommand
