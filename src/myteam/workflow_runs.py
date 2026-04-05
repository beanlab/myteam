"""Workflow run-state persistence and token accounting."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .paths import ENCODING, agents_root
from .workflow_definition import WorkflowDefinition, WorkflowError

WORKFLOW_RUNS_DIRNAME = "workflow_runs"


def zero_token_usage() -> dict[str, int]:
    return {
        "total_tokens": 0,
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
    }


def add_token_usage(current: dict[str, int], update: dict[str, int]) -> dict[str, int]:
    merged = dict(current)
    for key in merged:
        merged[key] += int(update.get(key, 0))
    return merged


def format_token_usage(token_usage: dict[str, int]) -> str:
    return (
        "total={total_tokens}, input={input_tokens}, cached_input={cached_input_tokens}, "
        "output={output_tokens}, reasoning_output={reasoning_output_tokens}"
    ).format(**token_usage)


@dataclass
class WorkflowStepAttempt:
    thread_id: str
    turn_id: str | None = None
    turn_ids: list[str] = field(default_factory=list)
    status: str = "in_progress"
    started_at: str = field(default_factory=lambda: utc_now())
    resolved_inputs: dict[str, Any] = field(default_factory=dict)
    final_message: str | None = None
    output: dict[str, Any] | None = None
    error: str | None = None
    token_usage: dict[str, int] = field(default_factory=zero_token_usage)
    finished_at: str | None = None
    last_conversation_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "turn_id": self.turn_id,
            "turn_ids": self.turn_ids,
            "status": self.status,
            "started_at": self.started_at,
            "resolved_inputs": self.resolved_inputs,
            "final_message": self.final_message,
            "output": self.output,
            "error": self.error,
            "token_usage": self.token_usage,
            "finished_at": self.finished_at,
            "last_conversation_message": self.last_conversation_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowStepAttempt":
        return cls(
            thread_id=str(data["thread_id"]),
            turn_id=data.get("turn_id"),
            turn_ids=list(data.get("turn_ids", [])),
            status=str(data.get("status", "in_progress")),
            started_at=str(data.get("started_at", utc_now())),
            resolved_inputs=dict(data.get("resolved_inputs", {})),
            final_message=data.get("final_message"),
            output=data.get("output"),
            error=data.get("error"),
            token_usage=dict(data.get("token_usage", zero_token_usage())),
            finished_at=data.get("finished_at"),
            last_conversation_message=data.get("last_conversation_message"),
        )


@dataclass
class WorkflowRunState:
    run_id: str
    workflow_path: str
    status: str
    next_step_index: int
    created_at: str
    updated_at: str
    current_step_id: str | None = None
    completed_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    attempts: dict[str, list[WorkflowStepAttempt]] = field(default_factory=dict)
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow_path": self.workflow_path,
            "status": self.status,
            "next_step_index": self.next_step_index,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "current_step_id": self.current_step_id,
            "completed_outputs": self.completed_outputs,
            "attempts": {
                step_id: [attempt.to_dict() for attempt in attempts]
                for step_id, attempts in self.attempts.items()
            },
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowRunState":
        return cls(
            run_id=str(data["run_id"]),
            workflow_path=str(data["workflow_path"]),
            status=str(data["status"]),
            next_step_index=int(data["next_step_index"]),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
            current_step_id=data.get("current_step_id"),
            completed_outputs=dict(data.get("completed_outputs", {})),
            attempts={
                step_id: [WorkflowStepAttempt.from_dict(attempt) for attempt in attempts]
                for step_id, attempts in dict(data.get("attempts", {})).items()
            },
            last_error=data.get("last_error"),
        )


def create_run_state(workflow: WorkflowDefinition) -> WorkflowRunState:
    now = utc_now()
    return WorkflowRunState(
        run_id=f"wr_{uuid.uuid4().hex[:10]}",
        workflow_path=str(workflow.path),
        status="in_progress",
        next_step_index=0,
        created_at=now,
        updated_at=now,
    )


def load_run_state(project_root: Path, run_id: str) -> WorkflowRunState:
    state_path = run_dir(project_root, run_id) / "run.json"
    try:
        data = json.loads(state_path.read_text(encoding=ENCODING))
    except OSError as exc:
        raise WorkflowError(f"failed to read workflow run {run_id}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"workflow run {run_id} is invalid: {exc}") from exc
    return WorkflowRunState.from_dict(data)


def save_run_state(project_root: Path, run_state: WorkflowRunState) -> None:
    workflow_run_dir = run_dir(project_root, run_state.run_id)
    workflow_run_dir.mkdir(parents=True, exist_ok=True)
    run_state.updated_at = utc_now()
    (workflow_run_dir / "run.json").write_text(
        json.dumps(run_state.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding=ENCODING,
    )


def workflow_token_usage(run_state: WorkflowRunState) -> dict[str, int]:
    total = zero_token_usage()
    for attempts in run_state.attempts.values():
        for attempt in attempts:
            if attempt.status != "completed":
                continue
            total = add_token_usage(total, attempt.token_usage)
    return total


def run_dir(project_root: Path, run_id: str) -> Path:
    return agents_root(project_root) / WORKFLOW_RUNS_DIRNAME / run_id


def utc_now() -> str:
    return datetime.now(UTC).isoformat()
