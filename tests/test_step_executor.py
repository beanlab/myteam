from __future__ import annotations

import json

from myteam.workflow.models import PtyRunResult, RunContext
from myteam.workflow.step_executor import execute_step


def test_execute_step_returns_completed_result_for_valid_completion(monkeypatch):
    seen = {}

    def fake_run_pty_session(argv, initial_input, on_output, **kwargs):
        del kwargs
        seen["argv"] = argv
        seen["initial_input"] = initial_input
        chunks = [
            b"working...\n",
            json.dumps(
                {
                    "status": "OBJECTIVE_COMPLETE",
                    "content": {"summary": {"title": "Done"}},
                }
            ).encode("utf-8"),
            b"\ntrailing output\n",
        ]
        responses = [on_output(chunk) for chunk in chunks]
        seen["responses"] = responses
        return PtyRunResult(
            exit_code=0,
            transcript=b"".join(chunks).decode("utf-8"),
        )

    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)

    result = execute_step(
        "review",
        {
            "prompt": "Review the draft.",
            "input": {"draft": "$draft.output"},
            "output": {"summary": {"title": "Result title"}},
        },
        RunContext(
            prior_steps={
                "draft": {
                    "prompt": "write draft",
                    "input": None,
                    "agent": "codex",
                    "output": {"title": "Draft Title"},
                }
            },
            default_agent="codex",
        ),
    )

    assert result.status == "completed"
    assert result.input == {"draft": {"title": "Draft Title"}}
    assert result.agent == "codex"
    assert result.output == {"summary": {"title": "Done"}}
    assert seen["argv"] == ["codex"]
    assert "Review the draft." in seen["initial_input"]
    assert "Draft Title" in seen["initial_input"]
    assert "OBJECTIVE_COMPLETE" in seen["initial_input"]
    assert seen["responses"][1] == "/quit\r"


def test_execute_step_fails_when_completion_json_never_arrives(monkeypatch):
    def fake_run_pty_session(argv, initial_input, on_output, **kwargs):
        del argv, initial_input, kwargs
        on_output(b"working...\n")
        return PtyRunResult(exit_code=0, transcript="working...\n")

    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)

    result = execute_step(
        "review",
        {
            "prompt": "Review the draft.",
            "output": {"summary": {"title": "Result title"}},
        },
        RunContext(prior_steps={}, default_agent="codex"),
    )

    assert result.status == "failed"
    assert result.error_type == "step_execution_error"
    assert "valid completion JSON" in result.error_message


def test_execute_step_ignores_earlier_json_and_accepts_final_completion_object(monkeypatch):
    def fake_run_pty_session(argv, initial_input, on_output, **kwargs):
        del argv, initial_input, kwargs
        chunks = [
            b'{"note":"intermediate"}\n',
            b"still working...\n",
            json.dumps(
                {
                    "status": "OBJECTIVE_COMPLETE",
                    "content": {"summary": {"title": "Done"}},
                }
            ).encode("utf-8"),
        ]
        for chunk in chunks:
            on_output(chunk)
        return PtyRunResult(exit_code=0, transcript=b"".join(chunks).decode("utf-8"))

    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)

    result = execute_step(
        "review",
        {
            "prompt": "Review the draft.",
            "output": {"summary": {"title": "Result title"}},
        },
        RunContext(prior_steps={}, default_agent="codex"),
    )

    assert result.status == "completed"
    assert result.output == {"summary": {"title": "Done"}}


def test_execute_step_accepts_valid_completion_object_with_trailing_tty_output(monkeypatch):
    def fake_run_pty_session(argv, initial_input, on_output, **kwargs):
        del argv, initial_input, kwargs
        chunks = [
            json.dumps(
                {
                    "status": "OBJECTIVE_COMPLETE",
                    "content": {"summary": {"title": "Done"}},
                }
            ).encode("utf-8"),
            b"\r\n> waiting for next input\r\n",
        ]
        responses = [on_output(chunk) for chunk in chunks]
        assert responses[0] == "/quit\r"
        return PtyRunResult(exit_code=0, transcript=b"".join(chunks).decode("utf-8"))

    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)

    result = execute_step(
        "review",
        {
            "prompt": "Review the draft.",
            "output": {"summary": {"title": "Result title"}},
        },
        RunContext(prior_steps={}, default_agent="codex"),
    )

    assert result.status == "completed"
    assert result.output == {"summary": {"title": "Done"}}


def test_execute_step_accepts_completion_object_with_terminal_control_sequences(monkeypatch):
    def fake_run_pty_session(argv, initial_input, on_output, **kwargs):
        del argv, initial_input, kwargs
        chunk = (
            b"\x1b[?25l"
            b'{"status":"OBJECTIVE_COMPLETE","content":{"summary":{"title":"Done"}}}'
            b"\x1b[?25h"
        )
        response = on_output(chunk)
        assert response == "/quit\r"
        return PtyRunResult(exit_code=0, transcript=chunk.decode("utf-8", errors="replace"))

    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)

    result = execute_step(
        "review",
        {
            "prompt": "Review the draft.",
            "output": {"summary": {"title": "Result title"}},
        },
        RunContext(prior_steps={}, default_agent="codex"),
    )

    assert result.status == "completed"
    assert result.output == {"summary": {"title": "Done"}}


def test_execute_step_accepts_completion_object_with_literal_newlines_in_string(monkeypatch):
    def fake_run_pty_session(argv, initial_input, on_output, **kwargs):
        del argv, initial_input, kwargs
        chunk = (
            b'{"status":"OBJECTIVE_COMPLETE","content":{"update":"The workflow\n'
            b'runner is now available."}}'
        )
        response = on_output(chunk)
        assert response == "/quit\r"
        return PtyRunResult(exit_code=0, transcript=chunk.decode("utf-8", errors="replace"))

    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)

    result = execute_step(
        "review",
        {
            "prompt": "Review the draft.",
            "output": {"update": "Result text"},
        },
        RunContext(prior_steps={}, default_agent="codex"),
    )

    assert result.status == "completed"
    assert result.output == {"update": "The workflow\nrunner is now available."}


def test_execute_step_normalizes_crlf_exit_text_for_interactive_tty(monkeypatch):
    def fake_run_pty_session(argv, initial_input, on_output, **kwargs):
        del argv, initial_input, kwargs
        chunk = json.dumps(
            {
                "status": "OBJECTIVE_COMPLETE",
                "content": {"summary": {"title": "Done"}},
            }
        ).encode("utf-8")
        response = on_output(chunk)
        assert response == "/quit\r"
        return PtyRunResult(exit_code=0, transcript=chunk.decode("utf-8"))

    def fake_get_agent_config(name):
        del name
        return {
            "name": "codex",
            "argv": ["codex"],
            "exit_text": "/quit\r\n",
            "prompt_as_argument": False,
        }

    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)
    monkeypatch.setattr("myteam.workflow.step_executor.get_agent_config", fake_get_agent_config)

    result = execute_step(
        "review",
        {
            "prompt": "Review the draft.",
            "output": {"summary": {"title": "Result title"}},
        },
        RunContext(prior_steps={}, default_agent="codex"),
    )

    assert result.status == "completed"
    assert result.output == {"summary": {"title": "Done"}}


def test_execute_step_fails_when_output_shape_is_incomplete(monkeypatch):
    def fake_run_pty_session(argv, initial_input, on_output, **kwargs):
        del argv, initial_input, kwargs
        chunk = json.dumps(
            {
                "status": "OBJECTIVE_COMPLETE",
                "content": {"summary": {}},
            }
        ).encode("utf-8")
        on_output(chunk)
        return PtyRunResult(exit_code=0, transcript=chunk.decode("utf-8"))

    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)

    result = execute_step(
        "review",
        {
            "prompt": "Review the draft.",
            "output": {"summary": {"title": "Result title"}},
        },
        RunContext(prior_steps={}, default_agent="codex"),
    )

    assert result.status == "failed"
    assert result.error_type == "step_execution_error"
    assert "missing required key: title" in result.error_message


def test_execute_step_accepts_scalar_output_template(monkeypatch):
    def fake_run_pty_session(argv, initial_input, on_output, **kwargs):
        del argv, initial_input, kwargs
        chunk = json.dumps(
            {
                "status": "OBJECTIVE_COMPLETE",
                "content": "done",
            }
        ).encode("utf-8")
        on_output(chunk)
        return PtyRunResult(exit_code=0, transcript=chunk.decode("utf-8"))

    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)

    result = execute_step(
        "review",
        {
            "prompt": "Review the draft.",
            "output": "concise answer",
        },
        RunContext(prior_steps={}, default_agent="codex"),
    )

    assert result.status == "completed"
    assert result.output == "done"
