"""Implementation-level tests for workflow-result RPC reporting.

Public `myteam start` tests cover reported result text. These tests keep the
managed-workflow environment checks and RPC payload validation focused.
"""
from __future__ import annotations

import pytest

from myteam.workflows.execution.protocol import ENV_SOCKET, ENV_WORKFLOW_INVOCATION_ID, KIND_WORKFLOW_RESULT
from myteam.workflows.workflow_result import report_workflow_result


def test_report_workflow_result_requires_managed_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_SOCKET, raising=False)
    monkeypatch.delenv(ENV_WORKFLOW_INVOCATION_ID, raising=False)

    with pytest.raises(RuntimeError, match="No active myteam workflow"):
        report_workflow_result("hello\n")


def test_report_workflow_result_rejects_non_text() -> None:
    with pytest.raises(TypeError, match="string or None"):
        report_workflow_result({"hello": "world"})  # type: ignore[arg-type]


def test_report_workflow_result_sends_rpc(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, dict[str, object]]] = []

    class FakeRpcClient:
        def __init__(self, socket_path: str) -> None:
            self.socket_path = socket_path

        def call(self, kind: str, **payload: object) -> dict[str, object]:
            calls.append((self.socket_path, kind, payload))
            return {"ok": True}

    monkeypatch.setenv(ENV_SOCKET, "/tmp/myteam.sock")
    monkeypatch.setenv(ENV_WORKFLOW_INVOCATION_ID, "workflow-1")
    monkeypatch.setattr("myteam.workflows.workflow_result.RpcClient", FakeRpcClient)

    report_workflow_result("hello\n")
    report_workflow_result(None)

    assert calls == [
        ("/tmp/myteam.sock", KIND_WORKFLOW_RESULT, {"request_id": "workflow-1", "text": "hello\n"}),
        ("/tmp/myteam.sock", KIND_WORKFLOW_RESULT, {"request_id": "workflow-1", "text": None}),
    ]
