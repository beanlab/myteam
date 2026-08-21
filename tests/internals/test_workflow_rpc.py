from __future__ import annotations

import os
import threading
from pathlib import Path
from queue import Queue

import pytest

from myteam.workflows.execution.protocol import KIND_START_WORKFLOW, RpcClient
from myteam.workflows.execution.workflow_commands import Command, StartWorkflowCommand
from myteam.workflows.execution.workflow_rpc import WorkflowRpcServer
from myteam.workflows.execution.workflow_store import WorkflowStore


def test_workflow_rpc_server_accepts_start_workflow(tmp_path: Path):
    commands: Queue[Command] = Queue()
    closed = threading.Event()
    woke = False

    def wake():
        nonlocal woke
        woke = True

    server = WorkflowRpcServer(
        socket_path=_short_socket_path("accept"),
        store=WorkflowStore(),
        commands=commands,
        wake=wake,
        closed=closed,
    )
    server.start()
    try:
        response = RpcClient(server.socket_path).call(
            KIND_START_WORKFLOW,
            argv=["python", "workflow.py"],
            workflow_path=str((tmp_path / "workflow.py").resolve()),
            parent_session_id=None,
            parent_agent_nonce=None,
            cwd=str(tmp_path),
            input_json='{"ok": true}',
        )
    finally:
        closed.set()
        server.close()
        Path(server.socket_path).unlink(missing_ok=True)

    command = commands.get(timeout=1)
    assert isinstance(command, StartWorkflowCommand)
    assert response == {"ok": True, "request_id": command.request_id}
    assert command.argv == ["python", "workflow.py"]
    assert command.workflow_path == str((tmp_path / "workflow.py").resolve())
    assert command.parent_session_id is None
    assert command.parent_agent_nonce is None
    assert command.cwd == str(tmp_path)
    assert command.input_json == '{"ok": true}'
    assert woke is True


def test_workflow_rpc_server_rejects_invalid_start_payload(tmp_path: Path):
    commands: Queue[Command] = Queue()
    closed = threading.Event()
    server = WorkflowRpcServer(
        socket_path=_short_socket_path("reject"),
        store=WorkflowStore(),
        commands=commands,
        wake=lambda: None,
        closed=closed,
    )
    server.start()
    try:
        with pytest.raises(RuntimeError, match="start_workflow requires a non-empty argv list"):
            RpcClient(server.socket_path).call(KIND_START_WORKFLOW, argv=[])
    finally:
        closed.set()
        server.close()
        Path(server.socket_path).unlink(missing_ok=True)

    assert commands.empty()


def test_workflow_rpc_rejects_non_resolved_workflow_path(tmp_path: Path):
    commands: Queue[Command] = Queue()
    closed = threading.Event()
    server = WorkflowRpcServer(
        socket_path=_short_socket_path("relative-path"),
        store=WorkflowStore(),
        commands=commands,
        wake=lambda: None,
        closed=closed,
    )
    server.start()
    try:
        with pytest.raises(RuntimeError, match="workflow_path"):
            RpcClient(server.socket_path).call(
                KIND_START_WORKFLOW,
                argv=["python", "workflow.py"],
                workflow_path="workflow.py",
                parent_session_id=None,
                parent_agent_nonce=None,
                cwd=str(tmp_path),
                input_json=None,
            )
    finally:
        closed.set()
        server.close()
        Path(server.socket_path).unlink(missing_ok=True)

    assert commands.empty()


def test_workflow_rpc_registers_and_unregisters_agent_in_complete_snapshot(tmp_path: Path):
    commands: Queue[Command] = Queue()
    closed = threading.Event()
    store = WorkflowStore()
    server = WorkflowRpcServer(
        socket_path=_short_socket_path("agent-stack"),
        store=store,
        commands=commands,
        wake=lambda: None,
        closed=closed,
    )
    server.start()
    try:
        client = RpcClient(server.socket_path)
        start = client.call(
            KIND_START_WORKFLOW,
            argv=["python", "workflow.py"],
            workflow_path=str((tmp_path / "workflow.py").resolve()),
            parent_session_id=None,
            parent_agent_nonce=None,
            cwd=str(tmp_path),
            input_json=None,
        )
        store.mark_running(start["request_id"])
        payload = {
            "nonce": "agent-1",
            "workflow_invocation_id": start["request_id"],
            "parent_agent_nonce": None,
            "name": "Planner",
            "agent": "pi",
            "model": "model-x",
            "session_id": None,
        }
        assert client.call("register_agent", **payload) == {"ok": True}
        # Identical registration is idempotent; conflicting nonce reuse is not.
        assert client.call("register_agent", **payload) == {"ok": True}
        with pytest.raises(RuntimeError):
            client.call("register_agent", **{**payload, "name": "Other"})

        snapshot = client.call("get_stack")
        assert snapshot == {
            "ok": True,
            "complete": True,
            "entries": [
                {
                    "type": "workflow",
                    "depth": 0,
                    "workflow_path": str((tmp_path / "workflow.py").resolve()),
                },
                {"type": "agent", "depth": 1, "name": "Planner", "agent": "pi", "model": "model-x"},
            ],
        }
        assert client.call("unregister_agent", nonce="agent-1") == {"ok": True}
        assert client.call("unregister_agent", nonce="agent-1") == {"ok": True}
        assert client.call("get_stack")["entries"] == [
            {
                "type": "workflow",
                "depth": 0,
                "workflow_path": str((tmp_path / "workflow.py").resolve()),
            }
        ]
    finally:
        closed.set()
        server.close()
        Path(server.socket_path).unlink(missing_ok=True)


def _short_socket_path(name: str) -> str:
    path = f"/tmp/myteam-{os.getpid()}-{name}.sock"
    Path(path).unlink(missing_ok=True)
    return path
