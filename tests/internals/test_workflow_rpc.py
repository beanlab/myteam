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
            parent_session_id="parent-1",
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
    assert command.parent_session_id == "parent-1"
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


def _short_socket_path(name: str) -> str:
    path = f"/tmp/myteam-{os.getpid()}-{name}.sock"
    Path(path).unlink(missing_ok=True)
    return path
