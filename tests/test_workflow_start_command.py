from __future__ import annotations

from pathlib import Path

from myteam.workflow.terminal.control_channel import ControlChannel


def test_workflow_start_reads_json_from_stdin(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    nonce = "session-nonce-123"
    with ControlChannel(session_nonce=nonce) as channel:
        monkeypatch.setattr("sys.stdin.read", lambda: '{"feature_request":"Build X"}')

        result = run_myteam_inprocess(initialized_project, "workflow-start", "development", "--session-nonce", nonce)

        assert result.exit_code == 0
        assert "Workflow start request accepted." in result.stdout
        request = channel.wait(timeout=1)
        assert request is not None
        assert request.workflow == "development"
        assert request.input == {"feature_request": "Build X"}


def test_workflow_start_accepts_json_flag(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    nonce = "session-nonce-123"
    with ControlChannel(session_nonce=nonce) as channel:

        result = run_myteam_inprocess(
            initialized_project,
            "workflow-start",
            "development",
            "--session-nonce",
            nonce,
            "--json",
            '{"feature_request":"Build X"}',
        )

        assert result.exit_code == 0
        request = channel.wait(timeout=1)
        assert request is not None
        assert request.input == {"feature_request": "Build X"}
