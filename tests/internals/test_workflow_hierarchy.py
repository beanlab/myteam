"""Risk-focused hierarchy tests below the CLI boundary.

These cover atomic visibility and stale-state cleanup that are difficult to
exercise deterministically through terminal-driven workflows.
"""
from __future__ import annotations

import os
from pathlib import Path
from queue import Queue
import threading

import pytest

from myteam.workflows.execution.protocol import KIND_START_WORKFLOW, RpcClient
from myteam.workflows.execution.workflow_commands import Command
from myteam.workflows.execution.supervisor import Supervisor
from myteam.workflows.execution.workflow_rpc import WorkflowRpcServer
from myteam.workflows.execution.workflow_store import WorkflowStore


def _start_server(name: str, store: WorkflowStore):
    commands: Queue[Command] = Queue()
    closed = threading.Event()
    path = f"/tmp/myteam-{os.getpid()}-{name}.sock"
    Path(path).unlink(missing_ok=True)
    server = WorkflowRpcServer(
        socket_path=path,
        store=store,
        commands=commands,
        wake=lambda: None,
        closed=closed,
    )
    server.start()
    return server, commands, closed


def _start(client: RpcClient, path: Path, *, parent: str | None = None) -> str:
    return client.call(
        KIND_START_WORKFLOW,
        argv=["python", str(path)],
        workflow_path=str(path.resolve()),
        parent_session_id=parent,
        parent_agent_nonce=None,
        cwd=str(path.parent),
        input_json=None,
    )["request_id"]


def test_pending_workflows_are_invisible_and_completed_workflows_purge_sessions(tmp_path: Path) -> None:
    store = WorkflowStore()
    server, _commands, closed = _start_server("hierarchy-lifecycle", store)
    try:
        client = RpcClient(server.socket_path)
        workflow = (tmp_path / "workflow.py").resolve()
        request_id = _start(client, workflow)

        assert client.call("get_stack") == {"ok": True, "complete": True, "entries": []}

        store.mark_running(request_id)
        client.call(
            "register_agent",
            nonce="agent-1",
            workflow_invocation_id=request_id,
            parent_agent_nonce=None,
            name="Worker",
            agent="pi",
            model=None,
            session_id=None,
        )
        assert [entry["type"] for entry in client.call("get_stack")["entries"]] == ["workflow", "agent"]

        store.complete_exit_request(request_id, exit_code=0)
        assert client.call("get_stack") == {"ok": True, "complete": True, "entries": []}
    finally:
        closed.set()
        server.close()
        Path(server.socket_path).unlink(missing_ok=True)


def test_activation_barrier_blocks_immediate_child_snapshot_until_running(tmp_path: Path, monkeypatch) -> None:
    workflow = (tmp_path / "workflow.py").resolve()
    with Supervisor() as supervisor:
        client = RpcClient(supervisor.socket_path)
        request_id = _start(client, workflow)
        command = supervisor._commands.get(timeout=1)
        started = threading.Event()
        finished = threading.Event()
        result: list[object] = []

        def read_stack() -> None:
            started.set()
            try:
                result.append(client.call("get_stack"))
            except BaseException as exc:
                result.append(exc)
            finally:
                finished.set()

        def launch(_command, *, socket_path: str):
            thread = threading.Thread(target=read_stack)
            thread.start()
            assert started.wait(timeout=1)
            assert not finished.wait(timeout=0.1)
            return object()

        monkeypatch.setattr(supervisor._stack, "start", launch)
        supervisor._start_workflow(command)
        assert finished.wait(timeout=1)

    assert result == [{
        "ok": True,
        "complete": True,
        "entries": [{"type": "workflow", "depth": 0, "workflow_path": str(workflow)}],
    }]


def test_incomplete_branched_hierarchy_is_rejected_without_entries(tmp_path: Path) -> None:
    store = WorkflowStore()
    server, _commands, closed = _start_server("hierarchy-branch", store)
    try:
        client = RpcClient(server.socket_path)
        parent = _start(client, tmp_path / "parent.py")
        store.mark_running(parent)
        first = _start(client, tmp_path / "first.py", parent=parent)
        second = _start(client, tmp_path / "second.py", parent=parent)
        store.mark_running(first)
        store.mark_running(second)

        with pytest.raises(RuntimeError) as error:
            client.call("get_stack")
        assert "Unsupported RPC kind" not in str(error.value)
        assert any(word in str(error.value).lower() for word in ("hierarchy", "stack", "branch", "complete"))
    finally:
        closed.set()
        server.close()
        Path(server.socket_path).unlink(missing_ok=True)
