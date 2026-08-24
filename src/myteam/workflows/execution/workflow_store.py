"""Workflow request, result, and active hierarchy storage."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import secrets
import threading
from typing import Any, Iterator, Literal


@dataclass
class RequestRecord:
    request_id: str
    kind: Literal["workflow"]
    workflow_path: str
    status: Literal["pending", "running", "ok", "error", "exited"] = "pending"
    parent_session_id: str | None = None
    parent_agent_nonce: str | None = None
    result: Any = None
    workflow_result_parts: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentSessionRecord:
    nonce: str
    workflow_invocation_id: str
    parent_agent_nonce: str | None
    name: str
    agent: str
    model: str | None
    session_id: str | None


Node = tuple[Literal["workflow", "agent"], str]


class WorkflowStore:
    """Owns workflow results and the authoritative active hierarchy."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._requests: dict[str, RequestRecord] = {}
        self._results: dict[str, dict[str, Any]] = {}
        self._agents: dict[str, AgentSessionRecord] = {}

    @contextmanager
    def hierarchy_transaction(self) -> Iterator[None]:
        with self._lock:
            yield

    def create_request(
        self,
        *,
        workflow_path: str,
        parent_session_id: str | None = None,
        parent_agent_nonce: str | None = None,
    ) -> RequestRecord:
        record = RequestRecord(
            request_id=self.new_request_id(),
            kind="workflow",
            workflow_path=workflow_path,
            parent_session_id=parent_session_id,
            parent_agent_nonce=parent_agent_nonce,
        )
        with self._lock:
            self._requests[record.request_id] = record
        return record

    def validate_workflow_parent(
        self,
        parent_session_id: str | None,
        parent_agent_nonce: str | None,
    ) -> None:
        with self._lock:
            entries = self._snapshot_entries()
            if parent_session_id is None:
                if parent_agent_nonce is not None or entries:
                    raise ValueError("A top-level workflow cannot be nested in an active hierarchy.")
                return
            parent = self._requests.get(parent_session_id)
            if parent is None or parent.status != "running":
                raise ValueError("Nested workflow requires a running parent workflow.")
            expected: Node = (("agent", parent_agent_nonce) if parent_agent_nonce else
                              ("workflow", parent_session_id))
            if parent_agent_nonce is not None and parent_agent_nonce not in self._agents:
                raise ValueError("Unknown parent agent nonce.")
            if not entries or self._active_leaf() != expected:
                raise ValueError("Nested workflow parent is not the current hierarchy entry.")

    def mark_running(self, request_id: str) -> None:
        with self._lock:
            record = self._requests[request_id]
            if record.status != "pending":
                raise ValueError("Workflow is not pending.")
            record.status = "running"

    def register_agent(self, record: AgentSessionRecord) -> bool:
        with self._lock:
            existing = self._agents.get(record.nonce)
            if existing is not None:
                if existing != record:
                    raise ValueError("Agent nonce is already registered with different metadata.")
                return False
            workflow = self._requests.get(record.workflow_invocation_id)
            if workflow is None or workflow.status != "running":
                raise ValueError("Agent session requires a running containing workflow.")
            if record.parent_agent_nonce is not None and record.parent_agent_nonce not in self._agents:
                raise ValueError("Unknown parent agent nonce.")
            self._agents[record.nonce] = record
            try:
                self._snapshot_entries()
            except Exception:
                self._agents.pop(record.nonce, None)
                raise
            return True

    def unregister_agent(self, nonce: str) -> None:
        with self._lock:
            self._purge_agent_and_descendants(nonce)

    def stack_snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._snapshot_entries()

    def result_text(self, request_id: str) -> str:
        with self._lock:
            record = self._requests.get(request_id)
            return "" if record is None else "".join(record.workflow_result_parts)

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
            self._purge_workflow_agents(request_id)
            record.status = status if status in {"ok", "error", "exited"} else "ok"  # type: ignore[assignment]
            record.result = result
            return record.parent_session_id

    def complete_exit_request(self, request_id: str, *, exit_code: int) -> str | None:
        status = "ok" if exit_code == 0 else "exited"
        with self._lock:
            record = self._requests.get(request_id)
            result = {
                "exit_code": exit_code,
                "result_text": "" if record is None else "".join(record.workflow_result_parts),
            }
            self._results[request_id] = {"status": status, "result": result}
            if record is None:
                return None
            self._purge_workflow_agents(request_id)
            record.status = status
            record.result = result
            return record.parent_session_id

    def poll_result(self, message: dict[str, Any]) -> dict[str, Any]:
        request_id = message.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("poll_result requires request_id.")
        with self._lock:
            result = self._results.get(request_id)
            return {"ok": True, "ready": False} if result is None else {"ok": True, "ready": True, **result}

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

    def _active_leaf(self) -> Node:
        workflows = {key: value for key, value in self._requests.items() if value.status == "running"}
        nodes: set[Node] = {("workflow", key) for key in workflows}
        nodes.update(("agent", key) for key in self._agents)
        parents: set[Node] = set()
        for workflow in workflows.values():
            if workflow.parent_agent_nonce:
                parents.add(("agent", workflow.parent_agent_nonce))
            elif workflow.parent_session_id:
                parents.add(("workflow", workflow.parent_session_id))
        for agent in self._agents.values():
            parents.add(("agent", agent.parent_agent_nonce) if agent.parent_agent_nonce else
                        ("workflow", agent.workflow_invocation_id))
        leaves = nodes - parents
        if len(leaves) != 1:
            raise ValueError("Active hierarchy does not have one current entry.")
        return leaves.pop()

    def _purge_workflow_agents(self, workflow_id: str) -> None:
        roots = [agent.nonce for agent in self._agents.values() if agent.workflow_invocation_id == workflow_id]
        for nonce in roots:
            self._purge_agent_and_descendants(nonce)

    def _purge_agent_and_descendants(self, nonce: str) -> None:
        children = [agent.nonce for agent in self._agents.values() if agent.parent_agent_nonce == nonce]
        for child in children:
            self._purge_agent_and_descendants(child)
        self._agents.pop(nonce, None)

    def _snapshot_entries(self) -> list[dict[str, Any]]:
        workflows = {key: value for key, value in self._requests.items() if value.status == "running"}
        nodes: dict[Node, RequestRecord | AgentSessionRecord] = {
            **{("workflow", key): value for key, value in workflows.items()},
            **{("agent", key): value for key, value in self._agents.items()},
        }
        if not nodes:
            return []

        parents: dict[Node, Node | None] = {}
        for key, value in nodes.items():
            if key[0] == "workflow":
                assert isinstance(value, RequestRecord)
                parent = (("agent", value.parent_agent_nonce) if value.parent_agent_nonce else
                          (("workflow", value.parent_session_id) if value.parent_session_id else None))
            else:
                assert isinstance(value, AgentSessionRecord)
                parent = (("agent", value.parent_agent_nonce) if value.parent_agent_nonce else
                          ("workflow", value.workflow_invocation_id))
            if parent is not None and parent not in nodes:
                raise ValueError("Active hierarchy has a missing parent.")
            parents[key] = parent

        roots = [key for key, parent in parents.items() if parent is None]
        if len(roots) != 1:
            raise ValueError("Active hierarchy must have one complete root.")
        children: dict[Node, list[Node]] = {key: [] for key in nodes}
        for key, parent in parents.items():
            if parent is not None:
                children[parent].append(key)
        if any(len(values) > 1 for values in children.values()):
            raise ValueError("Active hierarchy is branched.")

        ordered: list[Node] = []
        current: Node | None = roots[0]
        while current is not None:
            if current in ordered:
                raise ValueError("Active hierarchy contains a cycle.")
            ordered.append(current)
            current = children[current][0] if children[current] else None
        if len(ordered) != len(nodes):
            raise ValueError("Active hierarchy is disconnected.")

        entries: list[dict[str, Any]] = []
        for depth, key in enumerate(ordered):
            value = nodes[key]
            if key[0] == "workflow":
                assert isinstance(value, RequestRecord)
                entries.append({"type": "workflow", "depth": depth, "workflow_path": value.workflow_path})
            else:
                assert isinstance(value, AgentSessionRecord)
                entry: dict[str, Any] = {"type": "agent", "depth": depth, "name": value.name, "agent": value.agent}
                if value.model is not None:
                    entry["model"] = value.model
                if value.session_id is not None:
                    entry["session_id"] = value.session_id
                entries.append(entry)
        return entries
