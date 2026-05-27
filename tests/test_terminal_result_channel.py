from __future__ import annotations

import json

import pytest

from myteam.workflow.terminal.result_channel import ResultChannel, submit_result_payload


def test_result_channel_accepts_first_valid_payload():
    with ResultChannel() as channel:
        submit_result_payload({"answer": "done"}, socket_path=channel.socket_path, token=channel.token)
        assert channel.wait(timeout=1) == {"answer": "done"}


def test_result_channel_rejects_invalid_token():
    with ResultChannel() as channel:
        with pytest.raises(ValueError, match="Invalid workflow result token"):
            submit_result_payload({"answer": "done"}, socket_path=channel.socket_path, token="wrong")


def test_result_channel_rejects_output_shape_mismatch_until_corrected():
    expected_format = {"answer": {}}

    def validate(payload):
        if not isinstance(payload, dict) or "answer" not in payload:
            return "output format mismatch\nRequired output format:\n" + json.dumps(expected_format, indent=2)
        if not isinstance(payload["answer"], dict):
            return "output format mismatch\nRequired output format:\n" + json.dumps(expected_format, indent=2)
        return None

    with ResultChannel(payload_validator=validate) as channel:
        with pytest.raises(ValueError, match="output format mismatch"):
            submit_result_payload({"wrong": "shape"}, socket_path=channel.socket_path, token=channel.token)

        assert channel.wait(timeout=0.1) is None

        submit_result_payload({"answer": {}}, socket_path=channel.socket_path, token=channel.token)
        assert channel.wait(timeout=1) == {"answer": {}}
