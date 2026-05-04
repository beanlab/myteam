from __future__ import annotations

from pathlib import Path

from myteam.workflow.terminal.result_channel import ResultChannel


def test_workflow_result_reads_json_from_stdin(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    with ResultChannel() as channel:
        monkeypatch.setenv("MYTEAM_RESULT_SOCKET", channel.socket_path)
        monkeypatch.setenv("MYTEAM_RESULT_TOKEN", channel.token)
        monkeypatch.setattr("sys.stdin.read", lambda: '{"answer":"done"}')

        result = run_myteam_inprocess(initialized_project, "workflow-result")

        assert result.exit_code == 0
        assert "Workflow result accepted." in result.stdout
        assert channel.wait(timeout=1) == {"answer": "done"}
