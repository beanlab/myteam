from __future__ import annotations

import sys
from pathlib import Path

import pytest

from myteam.workflows.execution.mothership import Mothership
from myteam.workflows.execution.protocol import RpcClient


def test_mothership_runs_workflow_process(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.py"
    workflow.write_text(
        "from myteam.workflows import report_workflow_result\n"
        "print('live log')\n"
        "report_workflow_result('{\"answer\": \"ok\"}\\n')\n",
        encoding="utf-8",
    )

    with Mothership() as mothership:
        request_id = mothership.start_top_level_workflow(
            argv=[sys.executable, str(workflow)],
            cwd=str(tmp_path),
            input_json=None,
        )
        result = mothership.run_until_complete(request_id)

    assert result == {
        "status": "ok",
        "result": {
            "exit_code": 0,
            "result_text": '{"answer": "ok"}\n',
            "transcript": "live log\n",
            "stderr_transcript": "",
        },
    }


def test_mothership_rejects_old_agent_session_rpc() -> None:
    with Mothership() as mothership:
        client = RpcClient(mothership.socket_path)
        with pytest.raises(RuntimeError, match="Unsupported RPC kind"):
            client.call("start_agent_session", argv=["agent"])
