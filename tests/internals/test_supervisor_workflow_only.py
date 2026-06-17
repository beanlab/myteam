"""Implementation-level tests for the workflow supervisor RPC boundary.

The supervisor owns TTY/process orchestration and rejects obsolete RPC calls;
these protocol checks are intentionally below the CLI layer for determinism.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from myteam.workflows.execution.supervisor import Supervisor
from myteam.workflows.execution.protocol import RpcClient


def test_supervisor_runs_workflow_process(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.py"
    workflow.write_text(
        "from myteam.workflows import report_workflow_result\n"
        "print('live log')\n"
        "report_workflow_result('{\"answer\": \"ok\"}')\n",
        encoding="utf-8",
    )

    with Supervisor() as supervisor:
        request_id = supervisor.start_top_level_workflow(
            argv=[sys.executable, str(workflow)],
            cwd=str(tmp_path),
            input_json=None,
        )
        result = supervisor.run_until_complete(request_id)

    assert result == {
        "status": "ok",
        "result": {
            "exit_code": 0,
            "result_text": '{"answer": "ok"}\n',
            "transcript": "live log\n",
            "stderr_transcript": "",
        },
    }


def test_supervisor_rejects_old_agent_session_rpc() -> None:
    with Supervisor() as supervisor:
        client = RpcClient(supervisor.socket_path)
        with pytest.raises(RuntimeError, match="Unsupported RPC kind"):
            client.call("start_agent_session", argv=["agent"])
