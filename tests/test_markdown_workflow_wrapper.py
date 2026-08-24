from __future__ import annotations

import json
from pathlib import Path

import pytest

from myteam.templates import workflow_markdown_wrapper
from myteam.workflows.results import SessionResult


def test_markdown_wrapper_passes_raw_body_and_source_path_to_run_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workflow = tmp_path / "review.md"
    workflow.write_text(
        "---\n"
        "type: workflow\n"
        "description: review something\n"
        "agent: fake-agent\n"
        "session_name: Frontmatter review\n"
        "model: fake-model\n"
        "reasoning: medium\n"
        "interactive: false\n"
        "input:\n"
        "  topic: topic to review\n"
        "output:\n"
        "  summary: short summary\n"
        "---\n"
        "Review {{ topic }}.\n",
        encoding="utf-8",
    )
    seen: dict[str, object] = {}

    def fake_run_agent(**kwargs: object) -> SessionResult:
        seen.update(kwargs)
        return SessionResult(
            exit_code=0,
            output={"summary": "ok"},
            usage=[],
            transcript="transcript",
            session_id="session-1",
        )

    reported: list[str | None] = []
    monkeypatch.setattr(workflow_markdown_wrapper, "run_agent", fake_run_agent)
    monkeypatch.setattr(workflow_markdown_wrapper, "report_workflow_result", reported.append)

    workflow_markdown_wrapper.main(workflow, '{"topic": "release"}', "./review.md")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert reported == [json.dumps({"summary": "ok"})]
    assert seen == {
        "prompt": "Review {{ topic }}.\n",
        "input": {"topic": "release"},
        "prompt_source_path": workflow,
        "output": {"summary": "short summary"},
        "agent": "fake-agent",
        "session_name": "Frontmatter review",
        "model": "fake-model",
        "reasoning": "medium",
        "interactive": False,
    }


@pytest.mark.parametrize(
    ("frontmatter_name", "config_name", "expected_name"),
    [
        ("", "Config name", ""),
        (None, "Config name", "Config name"),
        (None, None, "./docs/../docs/review.md"),
    ],
)
def test_markdown_wrapper_session_name_precedence_preserves_caller_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    frontmatter_name: str | None,
    config_name: str | None,
    expected_name: str,
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    workflow = docs / "review.md"
    name_line = "" if frontmatter_name is None else f"session_name: {json.dumps(frontmatter_name)}\n"
    workflow.write_text(
        f"---\ntype: workflow\n{name_line}---\nReview.\n",
        encoding="utf-8",
    )
    config_lines = [] if config_name is None else [f"  session_name: {config_name}\n"]
    (tmp_path / ".myteam.yaml").write_text(
        "defaults:\n" + "".join(config_lines),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    seen: dict[str, object] = {}

    def fake_run_agent(**kwargs: object) -> SessionResult:
        seen.update(kwargs)
        return SessionResult(exit_code=0, output=None, usage=[], transcript="", session_id=None)

    monkeypatch.setattr(workflow_markdown_wrapper, "run_agent", fake_run_agent)
    monkeypatch.setattr(workflow_markdown_wrapper, "report_workflow_result", lambda _value: None)

    workflow_markdown_wrapper.main(workflow.resolve(), "{}", "./docs/../docs/review.md")

    assert seen["session_name"] == expected_name
    assert seen["prompt_source_path"] == workflow.resolve()


def test_markdown_wrapper_passes_raw_body_even_without_input_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = tmp_path / "workflow.md"
    workflow.write_text(
        "---\n"
        "type: workflow\n"
        "description: example\n"
        "---\n"
        "Use {{ topic }}.\n",
        encoding="utf-8",
    )
    seen: dict[str, object] = {}

    def fake_run_agent(**kwargs: object) -> SessionResult:
        seen.update(kwargs)
        return SessionResult(exit_code=0, output=None, usage=[], transcript="", session_id=None)

    reported: list[str | None] = []
    monkeypatch.setattr(workflow_markdown_wrapper, "run_agent", fake_run_agent)
    monkeypatch.setattr(workflow_markdown_wrapper, "report_workflow_result", reported.append)

    workflow_markdown_wrapper.main(workflow, '{"topic": "release"}')

    assert reported == [None]
    assert seen["prompt"] == "Use {{ topic }}.\n"
    assert seen["input"] == {"topic": "release"}
    assert seen["prompt_source_path"] == workflow


def test_markdown_wrapper_reports_no_text_for_none_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workflow = tmp_path / "workflow.md"
    workflow.write_text("---\ntype: workflow\n---\nPrompt\n", encoding="utf-8")

    def fake_run_agent(**_kwargs: object) -> SessionResult:
        return SessionResult(exit_code=0, output=None, usage=[], transcript="hidden", session_id="hidden")

    reported: list[str | None] = []
    monkeypatch.setattr(workflow_markdown_wrapper, "run_agent", fake_run_agent)
    monkeypatch.setattr(workflow_markdown_wrapper, "report_workflow_result", reported.append)

    workflow_markdown_wrapper.main(workflow, "{}")

    assert capsys.readouterr().out == ""
    assert reported == [None]


def test_markdown_wrapper_rejects_non_object_input(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.md"
    workflow.write_text("---\ntype: workflow\n---\nPrompt\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Workflow input must be a JSON object"):
        workflow_markdown_wrapper.main(workflow, "[]")
