from __future__ import annotations

from myteam.workflows import agent_session
from myteam.workflows.commands import _build_agent_prompt


def test_agent_prompt_includes_nonce_instructions_when_output_is_none() -> None:
    prompt = "Do the work.\n"

    rendered = _build_agent_prompt(prompt, session_nonce="nonce-123", output_schema=None)

    assert rendered.startswith("Do the work.\n\n## myteam result reporting")
    assert "myteam result" in rendered
    assert "session nonce: nonce-123" in rendered
    assert "Expected result JSON shape" not in rendered


def test_agent_prompt_includes_result_instructions_when_output_schema_is_present() -> None:
    rendered = _build_agent_prompt(
        "Do the work.",
        session_nonce="nonce-123",
        output_schema={"summary": "short summary"},
    )

    assert rendered.startswith("Do the work.\n\n## myteam result reporting")
    assert "myteam result" in rendered
    assert "session nonce: nonce-123" in rendered
    assert "Expected result JSON shape" in rendered
    assert '"summary": "short summary"' in rendered


def test_agent_prompt_renders_instruction_template_with_jinja(monkeypatch) -> None:
    monkeypatch.setattr(
        agent_session.templates,
        "get_template",
        lambda name: "nonce={{ SESSION_NONCE }}\nsection={{ OUTPUT_SCHEMA_SECTION }}",
    )

    rendered = _build_agent_prompt(
        "Do the work.",
        session_nonce="nonce-123",
        output_schema={"summary": "short summary"},
    )

    assert "nonce=nonce-123" in rendered
    assert "section=\nExpected result JSON shape:" in rendered
