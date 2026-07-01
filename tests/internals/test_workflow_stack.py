from __future__ import annotations

from typing import Any

import pytest

from myteam.workflows.execution.protocol import ENV_SOCKET, ENV_WORKFLOW_INPUT_JSON, ENV_WORKFLOW_INVOCATION_ID
from myteam.workflows.execution.workflow_commands import StartWorkflowCommand
from myteam.workflows.execution.workflow_stack import WorkflowStack, WorkflowStartError


class FakeTerminal:
    def __init__(self) -> None:
        self.flush_count = 0
        self.output = b""

    def flush_input(self):
        self.flush_count += 1

    def winsize(self) -> tuple[int, int]:
        return (24, 80)

    def write_stdout(self, data: bytes):
        self.output += data


class FakeSession:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.suspended = False
        self.resumed = False
        self.terminated = False
        self.closed = False
        self.resized_to: tuple[int, int] | None = None

    def suspend(self):
        self.suspended = True

    def resume(self):
        self.resumed = True

    def terminate(self):
        self.terminated = True

    def close(self):
        self.closed = True

    def resize(self, winsize: tuple[int, int]):
        self.resized_to = winsize


def test_workflow_stack_rejects_child_when_parent_is_not_active() -> None:
    stack = WorkflowStack(FakeTerminal())  # type: ignore[arg-type]
    stack.active = FakeSession("parent-1")  # type: ignore[assignment]

    with pytest.raises(WorkflowStartError) as error:
        stack.start(_command(parent_session_id="other-parent"), socket_path="/tmp/workflow.sock")

    assert error.value.result_payload == {
        "exit_code": 1,
        "result_text": "",
        "error_text": "Parent workflow is not the active managed workflow.\n",
    }


def test_workflow_stack_rejects_second_top_level_workflow() -> None:
    stack = WorkflowStack(FakeTerminal())  # type: ignore[arg-type]
    stack.active = FakeSession("active")  # type: ignore[assignment]

    with pytest.raises(WorkflowStartError) as error:
        stack.start(_command(parent_session_id=None), socket_path="/tmp/workflow.sock")

    assert error.value.result_payload == {
        "exit_code": 1,
        "result_text": "",
        "error_text": "Another workflow is already active.\n",
    }


def test_workflow_stack_suspends_child_parent_and_resumes(monkeypatch: pytest.MonkeyPatch) -> None:
    terminal = FakeTerminal()
    stack = WorkflowStack(terminal)  # type: ignore[arg-type]
    parent = FakeSession("parent-1")
    child = FakeSession("child-1")
    stack.active = parent  # type: ignore[assignment]

    monkeypatch.setattr(
        "myteam.workflows.execution.workflow_stack.ManagedPtyProcess.launch",
        lambda **_kwargs: child,
    )

    session = stack.start(_command(request_id="child-1", parent_session_id="parent-1"), socket_path="/tmp/workflow.sock")

    assert session is child
    assert parent.suspended is True
    assert stack.stack == [parent]
    assert stack.active is child
    assert stack.sessions == {"child-1": child}

    assert stack.resume_previous() is True
    assert parent.resumed is True
    assert stack.active is parent
    assert stack.stack == []


def test_workflow_stack_launches_with_supervisor_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    stack = WorkflowStack(FakeTerminal())  # type: ignore[arg-type]
    child = FakeSession("request-1")

    def fake_launch(**kwargs: Any) -> FakeSession:
        captured.update(kwargs)
        return child

    monkeypatch.setattr("myteam.workflows.execution.workflow_stack.ManagedPtyProcess.launch", fake_launch)

    stack.start(_command(input_json='{"answer": 42}'), socket_path="/tmp/workflow.sock")

    assert captured["session_id"] == "request-1"
    assert captured["request_id"] == "request-1"
    assert captured["argv"] == ["python", "workflow.py"]
    assert captured["cwd"] == "/tmp"
    assert captured["winsize"] == (24, 80)
    assert captured["merge_stderr"] is False
    assert captured["env"][ENV_SOCKET] == "/tmp/workflow.sock"
    assert captured["env"][ENV_WORKFLOW_INVOCATION_ID] == "request-1"
    assert captured["env"][ENV_WORKFLOW_INPUT_JSON] == '{"answer": 42}'
    assert stack.active is child
    assert stack.sessions == {"request-1": child}


def test_workflow_stack_resizes_and_closes_sessions() -> None:
    stack = WorkflowStack(FakeTerminal())  # type: ignore[arg-type]
    first = FakeSession("first")
    second = FakeSession("second")
    stack.sessions = {"first": first, "second": second}  # type: ignore[assignment]

    stack.resize((40, 120))
    stack.close_all()

    assert first.resized_to == (40, 120)
    assert second.resized_to == (40, 120)
    assert first.terminated is True
    assert second.terminated is True
    assert first.closed is True
    assert second.closed is True


def _command(
    *,
    request_id: str = "request-1",
    parent_session_id: str | None = None,
    input_json: str | None = None,
) -> StartWorkflowCommand:
    return StartWorkflowCommand(
        request_id=request_id,
        argv=["python", "workflow.py"],
        parent_session_id=parent_session_id,
        cwd="/tmp",
        input_json=input_json,
    )
