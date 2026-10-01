from __future__ import annotations

from myteam.workflows import agent_session
from myteam.workflows.agent_session import build_agent_system_prompt


def test_agent_system_prompt_includes_nonce_and_caller_content_without_output_schema() -> None:
    rendered = build_agent_system_prompt(
        "System instructions.\n",
        session_nonce="nonce-123",
        output_schema=None,
    )

    assert "nonce-123" in rendered
    assert "System instructions." in rendered
    assert "summary" not in rendered
    assert "short summary" not in rendered


def test_agent_system_prompt_includes_output_schema_source_when_present() -> None:
    rendered = build_agent_system_prompt(
        "System instructions.",
        session_nonce="nonce-123",
        output_schema={"summary": "short summary"},
    )

    assert "nonce-123" in rendered
    assert "System instructions." in rendered
    assert "summary" in rendered
    assert "short summary" in rendered


def test_agent_system_prompt_renders_instruction_template_with_schema_yaml_source(monkeypatch) -> None:
    monkeypatch.setattr(
        agent_session.templates,
        "get_template",
        lambda name: "schema={{ OUTPUT_SCHEMA_YAML }}",
    )

    rendered = build_agent_system_prompt(
        "System instructions.",
        session_nonce="nonce-123",
        output_schema={"summary": "short summary"},
    )

    assert "nonce-123" in rendered
    assert "System instructions." in rendered
    assert "schema=" in rendered
    assert "summary" in rendered
    assert "short summary" in rendered
    assert "{{ OUTPUT_SCHEMA_YAML }}" not in rendered
    assert "OUTPUT_SCHEMA_JSON" not in rendered


def test_agent_system_prompt_distinguishes_yaml_schema_from_json_result_reporting() -> None:
    rendered = build_agent_system_prompt(
        "System instructions.",
        session_nonce="nonce-123",
        output_schema={1: "numeric key", "completed_at": "date"},
    )

    assert "```yaml" in rendered
    assert "\n1: numeric key" in rendered
    assert "valid JSON" in rendered
    assert "OUTPUT_SCHEMA_JSON" not in rendered
