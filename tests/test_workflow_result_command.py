from __future__ import annotations

from pathlib import Path

from myteam.workflow.terminal.result_channel import ResultChannel


def test_workflow_result_reads_json_from_stdin(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    nonce = "session-nonce-123"
    with ResultChannel(session_nonce=nonce) as channel:
        monkeypatch.setattr("sys.stdin.read", lambda: '{"answer":"done"}')

        result = run_myteam_inprocess(initialized_project, "workflow-result", "--session-nonce", nonce)

        assert result.exit_code == 0
        assert "Workflow result accepted." in result.stdout
        assert channel.wait(timeout=1) == {"answer": "done"}
