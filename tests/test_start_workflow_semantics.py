from __future__ import annotations

import sys
from pathlib import Path

import pytest

from myteam.workflows.commands import (
    _build_workflow_argv,
    _start_workflow_result,
    start_workflow,
    start_workflow_cli,
)
from myteam.templates import get_template_file


def test_build_workflow_argv_requires_target() -> None:
    with pytest.raises(RuntimeError, match="requires a workflow file"):
        _build_workflow_argv(None, (), None)


def test_build_workflow_argv_rejects_missing_target() -> None:
    with pytest.raises(RuntimeError, match="does not exist"):
        _build_workflow_argv("missing.py", (), None)


def test_python_workflow_does_not_receive_injected_input(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.py"
    workflow.write_text("print('ok')\n", encoding="utf-8")

    argv = _build_workflow_argv(str(workflow), ("--custom", "value"), '{"topic": "release"}')

    assert argv == [sys.executable, str(workflow.resolve()), "--custom", "value"]


def test_markdown_workflow_receives_input_json(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.md"
    workflow.write_text("---\ntype: workflow\n---\nPrompt\n", encoding="utf-8")

    argv = _build_workflow_argv(str(workflow), ("extra",), '{"topic": "release"}')

    assert argv == [
        sys.executable,
        str(get_template_file("workflow_markdown_wrapper.py")),
        str(workflow.resolve()),
        '{"topic": "release"}',
        "extra",
    ]


def test_start_workflow_returns_explicit_workflow_result_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workflow = tmp_path / "workflow.py"
    workflow.write_text(
        "from myteam.workflows import report_workflow_result\n"
        "print('live log')\n"
        "report_workflow_result('first line')\n"
        "report_workflow_result('{\"not\": \"parsed\"}')\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result_text = start_workflow(str(workflow))

    assert result_text == 'first line\n{"not": "parsed"}\n'


def test_start_workflow_returns_empty_text_when_no_result_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workflow = tmp_path / "workflow.py"
    workflow.write_text("print('live only')\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result_text = start_workflow(str(workflow))

    assert result_text == ""


def test_start_workflow_cli_prints_result_text_and_exits_with_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workflow = tmp_path / "workflow.py"
    workflow.write_text(
        "import sys\n"
        "from myteam.workflows import report_workflow_result\n"
        "print('live out')\n"
        "print('live err', file=sys.stderr)\n"
        "report_workflow_result('result out')\n"
        "sys.exit(7)\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as excinfo:
        start_workflow_cli(str(workflow))

    captured = capsys.readouterr()
    assert excinfo.value.code == 7
    assert captured.out == "result out\n"
    assert captured.err == ""


def test_start_workflow_result_preserves_result_text_and_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workflow = tmp_path / "workflow.py"
    workflow.write_text(
        "import sys\n"
        "from myteam.workflows import report_workflow_result\n"
        "print('live out')\n"
        "print('live err', file=sys.stderr)\n"
        "report_workflow_result('explicit result')\n"
        "sys.exit(3)\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = _start_workflow_result(workflow_name=str(workflow), args=(), workflow_input_json=None)

    assert result.exit_code == 3
    assert result.result_text == "explicit result\n"
    assert result.error_text == ""
