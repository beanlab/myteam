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

    workflow_markdown_wrapper.main(workflow, '{"topic": "release"}')

    captured = capsys.readouterr()
    assert captured.out == ""
    assert reported == [json.dumps({"summary": "ok"})]
    assert seen == {
        "prompt": "Review {{ topic }}.\n",
        "input": {"topic": "release"},
        "prompt_source_path": workflow,
        "output": {"summary": "short summary"},
        "agent": "fake-agent",
        "model": "fake-model",
        "reasoning": "medium",
        "interactive": False,
    }


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
