from __future__ import annotations

from myteam.workflows import agent_session
from myteam.workflows.commands import _build_agent_prompt


def test_agent_prompt_includes_nonce_but_not_result_instructions_when_output_is_none() -> None:
    prompt = "Do the work.\n"

    rendered = _build_agent_prompt(prompt, session_nonce="nonce-123", output_schema=None)

    assert rendered.startswith("*Session ID: nonce-123*\n\nDo the work.")
    assert "## myteam session metadata" not in rendered
    assert "Session result reporting" not in rendered
    assert "myteam result" not in rendered


def test_agent_prompt_includes_result_instructions_when_output_schema_is_present() -> None:
    rendered = _build_agent_prompt(
        "Do the work.",
        session_nonce="nonce-123",
        output_schema={"summary": "short summary"},
    )

    assert rendered.startswith("*Session ID: nonce-123*\n\nDo the work.")
    assert "## myteam session metadata" not in rendered
    assert "Session result reporting" in rendered
    assert "myteam result" in rendered
    assert "The result JSON should follow this schema:" in rendered
    assert '```json\n{\n  "summary": "short summary"\n}\n```' in rendered


def test_agent_prompt_renders_instruction_template_with_jinja(monkeypatch) -> None:
    monkeypatch.setattr(
        agent_session.templates,
        "get_template",
        lambda name: "json={{ OUTPUT_SCHEMA_JSON }}",
    )

    rendered = _build_agent_prompt(
        "Do the work.",
        session_nonce="nonce-123",
        output_schema={"summary": "short summary"},
    )

    assert rendered.startswith("*Session ID: nonce-123*\n\nDo the work.")
    assert 'json={\n  "summary": "short summary"\n}' in rendered
    assert "```json" not in rendered
