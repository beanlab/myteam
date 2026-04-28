from __future__ import annotations

from typing import Any

from myteam.workflow.models import PtyRunResult
from myteam.workflow.step_executor import CompletionWatcher, execute_step


def test_completion_watcher_accepts_first_objective_complete_payload():
    watcher = CompletionWatcher()

    watcher.append(b'{"status":"INTERMEDIATE","content":{"message":"ignore"}}\n')
    watcher.append(b'{"status":"OBJECTIVE_COMPLETE","content":{"title":"first"}}\n')
    watcher.append(b'{"status":"OBJECTIVE_COMPLETE","content":{"title":"second"}}\n')

    assert watcher.completed is True
    assert watcher.content == {"title": "first"}


def test_completion_watcher_accepts_completion_across_chunk_boundaries():
    watcher = CompletionWatcher()

    watcher.append(b'{"status":"OBJECT')
    watcher.append(b'IVE_COMPLETE","content":{"title":"split"}}')

    assert watcher.completed is True
    assert watcher.content == {"title": "split"}


def test_completion_watcher_repairs_raw_newlines_inside_json_strings():
    watcher = CompletionWatcher()

    watcher.append(
        b'{"status":"OBJECTIVE_COMPLETE","content":{"title":"wrapped\nvalue","body":"ok"}}'
    )

    assert watcher.completed is True
    assert watcher.content == {"title": "wrappedvalue", "body": "ok"}


def test_completion_watcher_preserves_escaped_newlines_inside_json_strings():
    watcher = CompletionWatcher()

    watcher.append(
        b'{"status":"OBJECTIVE_COMPLETE","content":{"title":"line one\\nline two","body":"ok"}}'
    )

    assert watcher.completed is True
    assert watcher.content == {"title": "line one\nline two", "body": "ok"}


def test_completion_watcher_accepts_ansi_wrapped_completion_payload():
    watcher = CompletionWatcher()

    watcher.append(
        (
            b'\x1b[2m\xe2\x80\xa2 \x1b[22m{"status":"OBJECTIVE_COMPLETE","content":{"title":"A flooded stone shrine\r\n'
            b'\x1b[;m\x1b[K  beneath an old mill","body":"ok"}}\x1b[m'
        )
    )

    assert watcher.completed is True
    assert watcher.content == {
        "title": "A flooded stone shrine beneath an old mill",
        "body": "ok",
    }


def test_completion_watcher_ignores_non_completion_json_before_final_payload():
    watcher = CompletionWatcher()

    watcher.append(b'{"status":"INTERMEDIATE","content":{"title":"ignore me"}}\n')
    watcher.append(b'{"status":"OBJECT')
    watcher.append(b'IVE_COMPLETE","content":{"title":"keep me"}}\n')

    assert watcher.completed is True
    assert watcher.content == {"title": "keep me"}


def test_completion_watcher_ignores_stray_unmatched_brace_before_completion_payload():
    watcher = CompletionWatcher()

    watcher.append(b"Here is some prose with an unmatched brace {\n")
    watcher.append(b'{"status":"OBJECTIVE_COMPLETE","content":{"title":"final"}}')

    assert watcher.completed is True
    assert watcher.content == {"title": "final"}


def test_completion_watcher_rejects_completion_payload_with_extra_top_level_keys():
    watcher = CompletionWatcher()

    watcher.append(
        b'{"status":"OBJECTIVE_COMPLETE","content":{"title":"final"},"extra":"nope"}'
    )

    assert watcher.completed is False
    assert watcher.content is None


def test_completion_watcher_waits_for_closing_brace_before_accepting_completion():
    watcher = CompletionWatcher()

    watcher.append(b'{"status":"OBJECTIVE_COMPLETE","content":{"title":"partial"}')

    assert watcher.completed is False

    watcher.append(b"}")

    assert watcher.completed is True
    assert watcher.content == {"title": "partial"}


def test_completion_watcher_prefers_most_recent_completion_attempt():
    watcher = CompletionWatcher()

    watcher.append(b'{"status":"OBJECTIVE_COMPLETE","content":}\n')
    assert watcher.completed is False

    watcher.append(b'{"status":"OBJECTIVE_COMPLETE","content":{"title":"fixed"}}')

    assert watcher.completed is True
    assert watcher.content == {"title": "fixed"}


def test_execute_step_returns_completed_result(monkeypatch):
    recorded_launch: dict[str, Any] = {}

    def fake_get_agent_config(_name: str | None) -> dict[str, Any]:
        return {
            "name": "fake-agent",
            "argv": ["fake-agent"],
            "exit_text": "/quit\n",
        }

    def fake_run_pty_session(
        argv: list[str],
        initial_input: str | None,
        on_output,
        *,
        inactivity_timeout_seconds: int,
        graceful_shutdown_timeout_seconds: int,
    ) -> PtyRunResult:
        recorded_launch["argv"] = argv
        recorded_launch["initial_input"] = initial_input
        assert inactivity_timeout_seconds == 300
        assert graceful_shutdown_timeout_seconds == 30

        chunk = b'{"status":"OBJECTIVE_COMPLETE","content":{"summary":"done"}}\n'
        injected = on_output(chunk)
        assert injected == "/quit\n"
        return PtyRunResult(exit_code=0, transcript=chunk.decode("utf-8"))

    monkeypatch.setattr("myteam.workflow.step_executor.get_agent_config", fake_get_agent_config)
    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)

    result = execute_step(
        "draft",
        {
            "prompt": "Write a summary.",
            "output": {
                "summary": "short summary",
            },
        },
        prior_steps={},
    )

    assert result.status == "completed"
    assert result.output == {"summary": "done"}
    prompt_text = recorded_launch["argv"][-1]
    assert recorded_launch["argv"][:-1] == ["fake-agent"]
    assert recorded_launch["initial_input"] is None
    assert "Objective:" in prompt_text
    assert "Output template (strict):" in prompt_text
    assert "Write a summary." in prompt_text
    assert "Input:" not in prompt_text
    assert result.resolved_input is None


def test_execute_step_returns_completed_result_for_ansi_wrapped_completion_output(monkeypatch):
    def fake_get_agent_config(_name: str | None) -> dict[str, Any]:
        return {
            "name": "fake-agent",
            "argv": ["fake-agent"],
            "exit_text": "/quit\n",
        }

    chunk = (
        b'\x1b[2m\xe2\x80\xa2 \x1b[22m{"status":"OBJECTIVE_COMPLETE","content":{"summary":"A flooded stone shrine\r\n'
        b'\x1b[;m\x1b[K  beneath an old mill"}}\x1b[m'
    )

    def fake_run_pty_session(
        argv: list[str],
        initial_input: str | None,
        on_output,
        *,
        inactivity_timeout_seconds: int,
        graceful_shutdown_timeout_seconds: int,
    ) -> PtyRunResult:
        injected = on_output(chunk)
        assert injected == "/quit\n"
        return PtyRunResult(exit_code=0, transcript=chunk.decode("utf-8"))

    monkeypatch.setattr("myteam.workflow.step_executor.get_agent_config", fake_get_agent_config)
    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)

    result = execute_step(
        "draft",
        {
            "prompt": "Write a summary.",
            "output": {
                "summary": "short summary",
            },
        },
        prior_steps={},
    )

    assert result.status == "completed"
    assert result.output == {"summary": "A flooded stone shrine beneath an old mill"}


def test_execute_step_omits_input_section_when_authored_input_is_null(monkeypatch):
    recorded_launch: dict[str, Any] = {}

    def fake_get_agent_config(_name: str | None) -> dict[str, Any]:
        return {
            "name": "fake-agent",
            "argv": ["fake-agent"],
            "exit_text": "/quit\n",
        }

    def fake_run_pty_session(
        argv: list[str],
        initial_input: str | None,
        on_output,
        *,
        inactivity_timeout_seconds: int,
        graceful_shutdown_timeout_seconds: int,
    ) -> PtyRunResult:
        recorded_launch["argv"] = argv
        recorded_launch["initial_input"] = initial_input
        chunk = b'{"status":"OBJECTIVE_COMPLETE","content":{"summary":"done"}}\n'
        on_output(chunk)
        return PtyRunResult(exit_code=0, transcript=chunk.decode("utf-8"))

    monkeypatch.setattr("myteam.workflow.step_executor.get_agent_config", fake_get_agent_config)
    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)

    result = execute_step(
        "draft",
        {
            "input": None,
            "prompt": "Write a summary.",
            "output": {
                "summary": "short summary",
            },
        },
        prior_steps={},
    )

    assert result.status == "completed"
    assert result.resolved_input is None
    assert recorded_launch["initial_input"] is None
    assert "Input:" not in recorded_launch["argv"][-1]


def test_execute_step_returns_failed_result_for_reference_resolution_errors(monkeypatch):
    result = execute_step(
        "draft",
        {
            "input": "$missing.output",
            "prompt": "Write a summary.",
            "output": {
                "summary": "short summary",
            },
        },
        prior_steps={},
    )

    assert result.status == "failed"
    assert result.error_type == "reference_resolution"
    assert "unknown step" in (result.error_message or "")


def test_execute_step_returns_failed_result_for_invalid_runtime_default_agent():
    result = execute_step(
        "draft",
        {
            "prompt": "Write a summary.",
            "output": {
                "summary": "short summary",
            },
        },
        prior_steps={},
        default_agent="missing-agent",
    )

    assert result.status == "failed"
    assert result.error_type == "agent_resolution"
    assert "Unknown workflow agent: missing-agent" in (result.error_message or "")


def test_execute_step_returns_failed_result_when_agent_launch_fails(monkeypatch):
    def fake_get_agent_config(_name: str | None) -> dict[str, Any]:
        return {
            "name": "fake-agent",
            "argv": ["fake-agent"],
            "exit_text": "/quit\n",
        }

    def fake_run_pty_session(*args, **kwargs):
        raise OSError("no such file or directory")

    monkeypatch.setattr("myteam.workflow.step_executor.get_agent_config", fake_get_agent_config)
    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)

    result = execute_step(
        "draft",
        {
            "prompt": "Write a summary.",
            "output": {
                "summary": "short summary",
            },
        },
        prior_steps={},
    )

    assert result.status == "failed"
    assert result.error_type == "agent_launch"
    assert "Failed to launch workflow agent" in (result.error_message or "")


def test_execute_step_returns_failed_result_on_timeout(monkeypatch):
    def fake_get_agent_config(_name: str | None) -> dict[str, Any]:
        return {
            "name": "fake-agent",
            "argv": ["fake-agent"],
            "exit_text": "/quit\n",
        }

    def fake_run_pty_session(*args, **kwargs):
        raise TimeoutError("became inactive for 5 seconds")

    monkeypatch.setattr("myteam.workflow.step_executor.get_agent_config", fake_get_agent_config)
    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)

    result = execute_step(
        "draft",
        {
            "prompt": "Write a summary.",
            "output": {
                "summary": "short summary",
            },
        },
        prior_steps={},
    )

    assert result.status == "failed"
    assert result.error_type == "timeout"
    assert "inactive" in (result.error_message or "")


def test_execute_step_returns_failed_result_when_completion_is_missing(monkeypatch):
    def fake_get_agent_config(_name: str | None) -> dict[str, Any]:
        return {
            "name": "fake-agent",
            "argv": ["fake-agent"],
            "exit_text": "/quit\n",
        }

    def fake_run_pty_session(
        argv: list[str],
        initial_input: str | None,
        on_output,
        *,
        inactivity_timeout_seconds: int,
        graceful_shutdown_timeout_seconds: int,
    ) -> PtyRunResult:
        assert argv[:-1] == ["fake-agent"]
        assert "Write a summary." in argv[-1]
        assert initial_input is None
        on_output(b"still thinking\n")
        return PtyRunResult(exit_code=0, transcript="still thinking\n")

    monkeypatch.setattr("myteam.workflow.step_executor.get_agent_config", fake_get_agent_config)
    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)

    result = execute_step(
        "draft",
        {
            "prompt": "Write a summary.",
            "output": {
                "summary": "short summary",
            },
        },
        prior_steps={},
    )

    assert result.status == "failed"
    assert result.error_type == "completion_missing"
    assert "valid completion JSON object" in (result.error_message or "")


def test_execute_step_returns_failed_result_when_completion_json_is_invalid(monkeypatch):
    def fake_get_agent_config(_name: str | None) -> dict[str, Any]:
        return {
            "name": "fake-agent",
            "argv": ["fake-agent"],
            "exit_text": "/quit\n",
        }

    transcript = '{"status":"OBJECTIVE_COMPLETE","content":\n'

    def fake_run_pty_session(
        argv: list[str],
        initial_input: str | None,
        on_output,
        *,
        inactivity_timeout_seconds: int,
        graceful_shutdown_timeout_seconds: int,
    ) -> PtyRunResult:
        on_output(transcript.encode("utf-8"))
        return PtyRunResult(exit_code=0, transcript=transcript)

    monkeypatch.setattr("myteam.workflow.step_executor.get_agent_config", fake_get_agent_config)
    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)

    result = execute_step(
        "draft",
        {
            "prompt": "Write a summary.",
            "output": {
                "summary": "short summary",
            },
        },
        prior_steps={},
    )

    assert result.status == "failed"
    assert result.error_type == "completion_invalid"
    assert "OBJECTIVE_COMPLETE" in (result.error_message or "")


def test_execute_step_returns_failed_result_when_nested_output_key_is_missing(monkeypatch):
    def fake_get_agent_config(_name: str | None) -> dict[str, Any]:
        return {
            "name": "fake-agent",
            "argv": ["fake-agent"],
            "exit_text": "/quit\n",
        }

    chunk = (
        b'{"status":"OBJECTIVE_COMPLETE","content":{"summary":{"title":"done"}}}\n'
    )

    def fake_run_pty_session(
        argv: list[str],
        initial_input: str | None,
        on_output,
        *,
        inactivity_timeout_seconds: int,
        graceful_shutdown_timeout_seconds: int,
    ) -> PtyRunResult:
        on_output(chunk)
        return PtyRunResult(exit_code=0, transcript=chunk.decode("utf-8"))

    monkeypatch.setattr("myteam.workflow.step_executor.get_agent_config", fake_get_agent_config)
    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)

    result = execute_step(
        "draft",
        {
            "prompt": "Write a summary.",
            "output": {
                "summary": {
                    "title": "short title",
                    "body": "short body",
                },
            },
        },
        prior_steps={},
    )

    assert result.status == "failed"
    assert result.error_type == "output_validation"
    assert "missing required key: body" in (result.error_message or "")


def test_execute_step_returns_failed_result_when_mapping_output_is_not_mapping(monkeypatch):
    def fake_get_agent_config(_name: str | None) -> dict[str, Any]:
        return {
            "name": "fake-agent",
            "argv": ["fake-agent"],
            "exit_text": "/quit\n",
        }

    chunk = b'{"status":"OBJECTIVE_COMPLETE","content":{"summary":"done"}}\n'

    def fake_run_pty_session(
        argv: list[str],
        initial_input: str | None,
        on_output,
        *,
        inactivity_timeout_seconds: int,
        graceful_shutdown_timeout_seconds: int,
    ) -> PtyRunResult:
        on_output(chunk)
        return PtyRunResult(exit_code=0, transcript=chunk.decode("utf-8"))

    monkeypatch.setattr("myteam.workflow.step_executor.get_agent_config", fake_get_agent_config)
    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)

    result = execute_step(
        "draft",
        {
            "prompt": "Write a summary.",
            "output": {
                "summary": {
                    "title": "short title",
                },
            },
        },
        prior_steps={},
    )

    assert result.status == "failed"
    assert result.error_type == "output_validation"
    assert "output.summary must be a mapping" in (result.error_message or "")


def test_execute_step_returns_failed_result_when_agent_fails_after_valid_output(monkeypatch):
    def fake_get_agent_config(_name: str | None) -> dict[str, Any]:
        return {
            "name": "fake-agent",
            "argv": ["fake-agent"],
            "exit_text": "/quit\n",
        }

    chunk = b'{"status":"OBJECTIVE_COMPLETE","content":{"summary":"done"}}\n'

    def fake_run_pty_session(
        argv: list[str],
        initial_input: str | None,
        on_output,
        *,
        inactivity_timeout_seconds: int,
        graceful_shutdown_timeout_seconds: int,
    ) -> PtyRunResult:
        injected = on_output(chunk)
        assert injected == "/quit\n"
        return PtyRunResult(exit_code=7, transcript=chunk.decode("utf-8"))

    monkeypatch.setattr("myteam.workflow.step_executor.get_agent_config", fake_get_agent_config)
    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)

    result = execute_step(
        "draft",
        {
            "prompt": "Write a summary.",
            "output": {
                "summary": "short summary",
            },
        },
        prior_steps={},
    )

    assert result.status == "failed"
    assert result.error_type == "agent_failure_after_output"
    assert "status 7" in (result.error_message or "")


def test_execute_step_requests_agent_exit_only_once_after_completion(monkeypatch):
    def fake_get_agent_config(_name: str | None) -> dict[str, Any]:
        return {
            "name": "fake-agent",
            "argv": ["fake-agent"],
            "exit_text": "/quit\n",
        }

    def fake_run_pty_session(
        argv: list[str],
        initial_input: str | None,
        on_output,
        *,
        inactivity_timeout_seconds: int,
        graceful_shutdown_timeout_seconds: int,
    ) -> PtyRunResult:
        assert argv[:-1] == ["fake-agent"]
        assert initial_input is None

        first_injected = on_output(
            b'{"status":"OBJECTIVE_COMPLETE","content":{"summary":"done"}}\n'
        )
        second_injected = on_output(b"Token usage: total=123\n")

        assert first_injected == "/quit\n"
        assert second_injected is None
        return PtyRunResult(
            exit_code=0,
            transcript='{"status":"OBJECTIVE_COMPLETE","content":{"summary":"done"}}\n'
            "Token usage: total=123\n",
        )

    monkeypatch.setattr("myteam.workflow.step_executor.get_agent_config", fake_get_agent_config)
    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)

    result = execute_step(
        "draft",
        {
            "prompt": "Write a summary.",
            "output": {
                "summary": "short summary",
            },
        },
        prior_steps={},
    )

    assert result.status == "completed"
    assert result.output == {"summary": "done"}
