from __future__ import annotations

from pathlib import Path

from myteam.workflow.definition.models import StepResult
from myteam.workflow.execution.runner import run_named_workflow


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


def test_python_child_workflow_resolves_from_nested_myteam_cwd(initialized_project: Path, monkeypatch):
    workflow_file = initialized_project / ".myteam" / "child.py"
    workflow_file.write_text(
        "def main():\n"
        "    return {'answer': 'ok'}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MYTEAM_PROJECT_ROOT", str(initialized_project / ".myteam"))
    monkeypatch.chdir(initialized_project / ".myteam")

    result = run_named_workflow("child")

    assert result.status == "completed"
    assert result.output == {"answer": "ok"}


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


def test_python_child_workflow_can_return_step_result(initialized_project: Path, monkeypatch):
    workflow_file = initialized_project / ".myteam" / "child.py"
    workflow_file.write_text(
        "from myteam.workflow.definition.models import StepResult\n"
        "\n"
        "def main():\n"
        "    return StepResult(status='completed', output={'answer': 'ok'}, agent_name='codex')\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(initialized_project)

    result = run_named_workflow("child")

    assert result.status == "completed"
    assert result.output == {"answer": "ok"}


def test_role_child_workflow_reports_missing_required_input(initialized_project: Path, monkeypatch):
    role_dir = initialized_project / ".myteam" / "role-as-workflow"
    role_dir.mkdir()
    (role_dir / "role.md").write_text(
        "Please review the request.\n",
        encoding="utf-8",
    )
    (role_dir / "load.py").write_text("print('ROLE PROMPT')\n", encoding="utf-8")
    monkeypatch.chdir(initialized_project)

    result = run_named_workflow("role-as-workflow")

    assert result.status == "failed"
    assert result.error_message is not None
    assert "input contract mismatch" in result.error_message
    assert "Required input shape:" in result.error_message
    assert "file: absolute path to the file to review" in result.error_message
    assert "Received: <none>." in result.error_message
    assert "Missing keys: file (absolute path to the file to review)." in result.error_message


def test_role_child_workflow_includes_parent_objective_in_prompt(initialized_project: Path, monkeypatch):
    role_dir = initialized_project / ".myteam" / "role-as-workflow"
    role_dir.mkdir()
    (role_dir / "role.md").write_text(
        "Please review the request.\n",
        encoding="utf-8",
    )
    (role_dir / "load.py").write_text("print('ROLE PROMPT')\n", encoding="utf-8")
    monkeypatch.chdir(initialized_project)

    seen: dict[str, object] = {}

    def fake_run_default_workflow(prompt: str, *, cwd: Path, workflow_settings):
        seen["prompt"] = prompt
        seen["cwd"] = cwd
        seen["workflow_settings"] = workflow_settings
        return StepResult(status="completed", output={"status": "completed"})

    monkeypatch.setattr("myteam.workflow.execution.runner.run_default_workflow", fake_run_default_workflow)

    result = run_named_workflow("role-as-workflow", parent_objective="Finish the parent task.")

    assert result.status == "completed"
    assert seen["cwd"] == role_dir
    assert seen["workflow_settings"] is None