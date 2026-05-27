from __future__ import annotations

import pytest

from myteam.workflow.terminal.control_channel import ControlChannel, submit_child_workflow_request


def test_control_channel_accepts_child_workflow_request():
    nonce = "session-nonce-123"
    with ControlChannel(session_nonce=nonce) as channel:
        submit_child_workflow_request(
            "development-workflow/development",
            {"feature_request": "Build X"},
            session_nonce=nonce,
        )

        request = channel.wait(timeout=1)

    assert request is not None
    assert request.workflow == "development-workflow/development"
    assert request.input == {"feature_request": "Build X"}


def test_control_channel_rejects_invalid_token():
    with ControlChannel() as channel:
        with pytest.raises(ValueError, match="Invalid workflow control token"):
            submit_child_workflow_request(
                "demo",
                socket_path=channel.socket_path,
                token="wrong",
            )


def test_control_channel_rejects_duplicate_request():
    with ControlChannel() as channel:
        submit_child_workflow_request("demo", socket_path=channel.socket_path, token=channel.token)
        with pytest.raises(ValueError, match="already recorded"):
            submit_child_workflow_request("other", socket_path=channel.socket_path, token=channel.token)


def test_submit_child_workflow_request_requires_connection_details(monkeypatch):
    monkeypatch.delenv("MYTEAM_CONTROL_SOCKET", raising=False)
    monkeypatch.delenv("MYTEAM_CONTROL_TOKEN", raising=False)

    with pytest.raises(ValueError, match="Missing session nonce or MYTEAM_CONTROL_SOCKET or MYTEAM_CONTROL_TOKEN"):
        submit_child_workflow_request("demo")
