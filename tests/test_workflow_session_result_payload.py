from myteam.workflows.commands import _session_result_from_payload


def test_raw_workflow_output_dict_becomes_session_output() -> None:
    result = _session_result_from_payload({"answer": "ok"})

    assert result.exit_code == 0
    assert result.output == {"answer": "ok"}
    assert result.usage == []
    assert result.transcript == ""
    assert result.session_id is None


def test_session_result_payload_preserves_usage_and_metadata() -> None:
    result = _session_result_from_payload(
        {
            "exit_code": 3,
            "output": {"answer": "ok"},
            "usage": [{"model": "test-model", "total_tokens": 7}],
            "transcript": "session transcript",
            "session_id": "native-session-id",
        }
    )

    assert result.exit_code == 3
    assert result.output == {"answer": "ok"}
    assert len(result.usage) == 1
    assert result.usage[0].model == "test-model"
    assert result.usage[0].total_tokens == 7
    assert result.transcript == "session transcript"
    assert result.session_id == "native-session-id"


def test_plain_output_field_is_not_mistaken_for_session_result_payload() -> None:
    result = _session_result_from_payload({"output": "literal output field"})

    assert result.exit_code == 0
    assert result.output == {"output": "literal output field"}


def test_no_payload_becomes_none_output() -> None:
    result = _session_result_from_payload(None)

    assert result.exit_code == 0
    assert result.output is None
    assert result.usage == []


def test_raw_non_dict_workflow_output_is_preserved() -> None:
    result = _session_result_from_payload("plain text")

    assert result.exit_code == 0
    assert result.output == "plain text"


def test_session_result_payload_preserves_non_dict_output() -> None:
    result = _session_result_from_payload(
        {
            "output": ["first", "second"],
            "usage": [],
            "transcript": "session transcript",
            "session_id": "native-session-id",
        }
    )

    assert result.exit_code == 0
    assert result.output == ["first", "second"]
    assert result.transcript == "session transcript"
    assert result.session_id == "native-session-id"


def test_session_result_payload_preserves_none_output() -> None:
    result = _session_result_from_payload(
        {
            "output": None,
            "usage": [],
            "transcript": "session transcript",
            "session_id": "native-session-id",
        }
    )

    assert result.exit_code == 0
    assert result.output is None
    assert result.transcript == "session transcript"
    assert result.session_id == "native-session-id"
