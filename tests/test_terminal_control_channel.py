from __future__ import annotations

import pytest

from myteam.tasks.terminal.control_channel import ControlChannel, submit_child_task_request


def test_control_channel_accepts_child_task_request():
    nonce = "session-nonce-123"
    with ControlChannel(session_nonce=nonce) as channel:
        submit_child_task_request(
            "development-workflow/development",
            {"feature_request": "Build X"},
            session_nonce=nonce,
        )

        request = channel.wait(timeout=1)

    assert request is not None
    assert request.task == "development-workflow/development"
    assert request.input == {"feature_request": "Build X"}


def test_control_channel_rejects_invalid_token():
    with ControlChannel() as channel:
        with pytest.raises(ValueError, match="Invalid workflow control token"):
            submit_child_task_request(
                "demo",
                socket_path=channel.socket_path,
                token="wrong",
            )


def test_control_channel_rejects_duplicate_request():
    with ControlChannel() as channel:
        submit_child_task_request("demo", socket_path=channel.socket_path, token=channel.token)
        with pytest.raises(ValueError, match="already recorded"):
            submit_child_task_request("other", socket_path=channel.socket_path, token=channel.token)


def test_submit_child_task_request_requires_connection_details():
    with pytest.raises(ValueError, match="Missing session nonce"):
        submit_child_task_request("demo")
