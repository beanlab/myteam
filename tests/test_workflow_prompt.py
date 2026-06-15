from __future__ import annotations

from myteam.workflows import agent_session
from myteam.workflows.commands import _build_agent_prompt


def test_agent_prompt_includes_nonce_and_original_prompt_without_output_schema_content() -> None:
    rendered = _build_agent_prompt(
        "Do the work.\n",
        session_nonce="nonce-123",
        output_schema=None,
    )

    assert "nonce-123" in rendered
    assert "Do the work." in rendered
    assert "summary" not in rendered
    assert "short summary" not in rendered


def test_agent_prompt_includes_output_schema_source_when_output_schema_is_present() -> None:
    rendered = _build_agent_prompt(
        "Do the work.",
        session_nonce="nonce-123",
        output_schema={"summary": "short summary"},
    )

    assert "nonce-123" in rendered
    assert "Do the work." in rendered
    assert "summary" in rendered
    assert "short summary" in rendered


def test_agent_prompt_renders_instruction_template_with_schema_json_source(monkeypatch) -> None:
    monkeypatch.setattr(
        agent_session.templates,
        "get_template",
        lambda name: "schema={{ OUTPUT_SCHEMA_JSON }}",
    )

    rendered = _build_agent_prompt(
        "Do the work.",
        session_nonce="nonce-123",
        output_schema={"summary": "short summary"},
    )

    assert "nonce-123" in rendered
    assert "Do the work." in rendered
    assert "schema=" in rendered
    assert "summary" in rendered
    assert "short summary" in rendered
    assert "{{ OUTPUT_SCHEMA_JSON }}" not in rendered
