"""Workflow request and result storage for the workflow supervisor."""
from __future__ import annotations

from dataclasses import dataclass, field
import secrets
import threading
from typing import Any, Literal


@dataclass
class RequestRecord:
    request_id: str
    kind: Literal["workflow"]
    status: Literal["pending", "running", "ok", "error", "exited"] = "pending"
    parent_session_id: str | None = None
    result: Any = None
    workflow_result_parts: list[str] = field(default_factory=list)


class WorkflowStore:
    """Owns workflow request records, explicit result text, and final results."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._requests: dict[str, RequestRecord] = {}
        self._results: dict[str, dict[str, Any]] = {}

    def create_request(self, *, parent_session_id: str | None = None) -> RequestRecord:
        request_id = self.new_request_id()
        record = RequestRecord(
            request_id=request_id,
            kind="workflow",
            status="pending",
            parent_session_id=parent_session_id,
        )
        with self._lock:
            self._requests[request_id] = record
        return record

    def mark_running(self, request_id: str) -> None:
        with self._lock:
            self._requests[request_id].status = "running"

    def result_text(self, request_id: str) -> str:
        with self._lock:
            record = self._requests.get(request_id)
            if record is None:
                return ""
            return "".join(record.workflow_result_parts)

    def get_result(self, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            result = self._results.get(request_id)
            return None if result is None else dict(result)

    def parent_session_id(self, request_id: str) -> str | None:
        with self._lock:
            record = self._requests.get(request_id)
            return None if record is None else record.parent_session_id

    def store_result(self, request_id: str, *, status: str, result: Any) -> None:
        self.complete_request(request_id, status=status, result=result)

    def complete_request(self, request_id: str, *, status: str, result: Any) -> str | None:
        with self._lock:
            self._results[request_id] = {"status": status, "result": result}
            record = self._requests.get(request_id)
            if record is None:
                return None
            record.status = status if status in {"ok", "error", "exited"} else "ok"  # type: ignore[assignment]
            record.result = result
            return record.parent_session_id

    def complete_exit_request(
        self,
        request_id: str,
        *,
        exit_code: int,
        transcript: str,
        stderr_transcript: str,
    ) -> str | None:
        status = "ok" if exit_code == 0 else "exited"
        with self._lock:
            record = self._requests.get(request_id)
            result = {
                "exit_code": exit_code,
                "result_text": "" if record is None else "".join(record.workflow_result_parts),
                "transcript": transcript,
                "stderr_transcript": stderr_transcript,
            }
            self._results[request_id] = {"status": status, "result": result}
            if record is None:
                return None
            record.status = status
            record.result = result
            return record.parent_session_id

    def poll_result(self, message: dict[str, Any]) -> dict[str, Any]:
        request_id = message.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("poll_result requires request_id.")
        with self._lock:
            result = self._results.get(request_id)
            if result is None:
                return {"ok": True, "ready": False}
            return {"ok": True, "ready": True, **result}

    def ack_result(self, message: dict[str, Any]) -> dict[str, Any]:
        request_id = message.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("ack_result requires request_id.")
        with self._lock:
            self._results.pop(request_id, None)
            self._requests.pop(request_id, None)
        return {"ok": True}

    def report_workflow_result(self, message: dict[str, Any]) -> dict[str, Any]:
        request_id = message.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("workflow_result requires request_id.")
        text = message.get("text")
        if text is not None and not isinstance(text, str):
            raise ValueError("workflow_result text must be a string or null.")
        with self._lock:
            record = self._requests.get(request_id)
            if record is None:
                raise ValueError("Unknown workflow request_id.")
            if record.status not in {"pending", "running"}:
                raise ValueError("Workflow is not active.")
            if text is not None:
                record.workflow_result_parts.append(text)
        return {"ok": True}

    def new_request_id(self) -> str:
        return secrets.token_urlsafe(12)
