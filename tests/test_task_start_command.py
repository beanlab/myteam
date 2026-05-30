from __future__ import annotations

from pathlib import Path

from myteam.tasks.terminal.control_channel import ControlChannel


def test_workflow_start_reads_json_from_stdin(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    nonce = "session-nonce-123"
    with ControlChannel(session_nonce=nonce) as channel:
        monkeypatch.setattr("sys.stdin.read", lambda: '{"feature_request":"Build X"}')

        result = run_myteam_inprocess(initialized_project, "task", "start", "development", "--session-nonce", nonce)

        assert result.exit_code == 0
        assert "Task start request accepted." in result.stdout
        request = channel.wait(timeout=1)
        assert request is not None
        assert request.task == "development"
        assert request.input == {"feature_request": "Build X"}


def test_workflow_start_accepts_json_flag(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    nonce = "session-nonce-123"
    with ControlChannel(session_nonce=nonce) as channel:

        result = run_myteam_inprocess(
            initialized_project,
            "task",
            "start",
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


def test_workflow_start_help_shows_session_nonce_flag(run_myteam_inprocess, initialized_project: Path):
    result = run_myteam_inprocess(initialized_project, "task", "start", "--help")

    assert result.exit_code == 0
    assert "--session-nonce" in result.stdout
    assert "--session_nonce" not in result.stdout


def test_workflow_start_rejects_underscore_session_nonce(run_myteam_inprocess, initialized_project: Path):
    result = run_myteam_inprocess(
        initialized_project,
        "task",
        "start",
        "development",
        "--session_nonce",
        "session-nonce-123",
    )

    assert result.exit_code == 2
    assert "--session-nonce" in result.stderr
