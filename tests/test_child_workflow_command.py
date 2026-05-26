from __future__ import annotations

from pathlib import Path

from myteam.workflow.terminal.control_channel import ControlChannel


def test_child_workflow_reads_json_from_stdin(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    with ControlChannel() as channel:
        monkeypatch.setenv("MYTEAM_CONTROL_SOCKET", channel.socket_path)
        monkeypatch.setenv("MYTEAM_CONTROL_TOKEN", channel.token)
        monkeypatch.setattr("sys.stdin.read", lambda: '{"feature_request":"Build X"}')

        result = run_myteam_inprocess(initialized_project, "child-workflow", "development")

        assert result.exit_code == 0
        assert "Child workflow request accepted." in result.stdout
        request = channel.wait(timeout=1)
        assert request is not None
        assert request.workflow == "development"
        assert request.input == {"feature_request": "Build X"}


def test_child_workflow_accepts_json_flag(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    with ControlChannel() as channel:
        monkeypatch.setenv("MYTEAM_CONTROL_SOCKET", channel.socket_path)
        monkeypatch.setenv("MYTEAM_CONTROL_TOKEN", channel.token)

        result = run_myteam_inprocess(
            initialized_project,
            "child-workflow",
            "development",
            "--json",
            '{"feature_request":"Build X"}',
        )

        assert result.exit_code == 0
        request = channel.wait(timeout=1)
        assert request is not None
        assert request.input == {"feature_request": "Build X"}
