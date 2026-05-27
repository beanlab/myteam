from __future__ import annotations

import json
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


def test_workflow_result_reports_output_format_mismatch(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    expected_format = {"answer": {}}

    def validate(payload):
        if not isinstance(payload, dict) or "answer" not in payload or not isinstance(payload["answer"], dict):
            return "output format mismatch\nRequired output format:\n" + json.dumps(expected_format, indent=2)
        return None

    with ResultChannel(payload_validator=validate) as channel:
        monkeypatch.setenv("MYTEAM_RESULT_SOCKET", channel.socket_path)
        monkeypatch.setenv("MYTEAM_RESULT_TOKEN", channel.token)
        monkeypatch.setattr("sys.stdin.read", lambda: '{"answer":"done"}')

        result = run_myteam_inprocess(initialized_project, "workflow-result")

        assert result.exit_code == 1
        assert "output format mismatch" in result.stderr
        assert "Required output format:" in result.stderr
        assert channel.wait(timeout=0.1) is None
