from __future__ import annotations

import pytest

from myteam.workflow.terminal.result_channel import ResultChannel, submit_result_payload


def test_result_channel_accepts_first_valid_payload():
    nonce = "session-nonce-123"
    with ResultChannel(session_nonce=nonce) as channel:
        submit_result_payload({"answer": "done"}, session_nonce=nonce)
        assert channel.wait(timeout=1) == {"answer": "done"}


def test_result_channel_rejects_invalid_token():
    with ResultChannel() as channel:
        with pytest.raises(ValueError, match="Invalid workflow result token"):
            submit_result_payload({"answer": "done"}, socket_path=channel.socket_path, token="wrong")


def test_submit_result_payload_requires_session_nonce():
    with pytest.raises(ValueError, match="Missing session nonce"):
        submit_result_payload({"answer": "done"})
