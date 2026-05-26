from __future__ import annotations

from pathlib import Path

from myteam.workflow.runner import run_named_workflow


def test_python_child_workflow_main_return_value_becomes_output(initialized_project: Path, monkeypatch):
    workflow_file = initialized_project / ".myteam" / "child.py"
    workflow_file.write_text(
        "def main(feature_request):\n"
        "    return {'answer': feature_request.upper()}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(initialized_project)

    result = run_named_workflow("child", input={"feature_request": "build x"})

    assert result.status == "completed"
    assert result.output == {"answer": "BUILD X"}


def test_python_child_workflow_none_return_gets_completion_output(initialized_project: Path, monkeypatch):
    workflow_file = initialized_project / ".myteam" / "child.py"
    workflow_file.write_text(
        "def main():\n"
        "    return None\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(initialized_project)

    result = run_named_workflow("child")

    assert result.status == "completed"
    assert result.output == {"status": "completed"}


def test_python_child_workflow_exception_returns_structured_failure(initialized_project: Path, monkeypatch):
    workflow_file = initialized_project / ".myteam" / "child.py"
    workflow_file.write_text(
        "def main():\n"
        "    raise RuntimeError('boom')\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(initialized_project)

    result = run_named_workflow("child")

    assert result.status == "failed"
    assert "boom" in (result.error_message or "")
