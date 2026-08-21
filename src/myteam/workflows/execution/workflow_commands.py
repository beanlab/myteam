"""Internal command messages for workflow supervisor coordination."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StartWorkflowCommand:
    request_id: str
    argv: list[str]
    workflow_path: str
    parent_session_id: str | None
    parent_agent_nonce: str | None
    cwd: str | None
    input_json: str | None


Command = StartWorkflowCommand
