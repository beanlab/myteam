from __future__ import annotations

from pathlib import Path

from myteam.workflow.definition.models import StepResult
from myteam.workflow.execution.steps import run_agent
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


def test_markdown_child_workflow_uses_prompt_body_and_frontmatter(initialized_project: Path, monkeypatch):
    workflow_file = initialized_project / ".myteam" / "child.md"
    workflow_file.write_text(
        "---\n"
        "name: Child task\n"
        "description: Summarize notes\n"
        "agent: codex\n"
        "output:\n"
        "  answer: ok\n"
        "---\n"
        "Summarize the attached notes.\n",
        encoding="utf-8",
    )

    seen: dict[str, object] = {}

    def fake_run_default_workflow(prompt: str, **kwargs):
        seen["prompt"] = prompt
        seen["kwargs"] = kwargs
        return StepResult(status="completed", output={"answer": "ok"})

    monkeypatch.setattr("myteam.workflow.execution.runner.run_default_workflow", fake_run_default_workflow)
    monkeypatch.chdir(initialized_project)

    result = run_named_workflow("child")

    assert result.status == "completed"
    assert result.output == {"answer": "ok"}
    assert seen["prompt"].strip()
    assert seen["kwargs"]["cwd"] == workflow_file.parent
    workflow_settings = seen["kwargs"]["workflow_settings"]
    assert workflow_settings.agent == "codex"
    assert workflow_settings.output == {"answer": "ok"}


def test_markdown_child_workflow_requires_caller_input_when_frontmatter_declares_it(
    initialized_project: Path,
    monkeypatch,
):
    workflow_file = initialized_project / ".myteam" / "child.md"
    workflow_file.write_text(
        "---\n"
        "name: Child task\n"
        "description: Needs input\n"
        "input:\n"
        "  topic: release\n"
        "---\n"
        "Summarize the attached notes.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(initialized_project)

    result = run_named_workflow("child")

    assert result.status == "failed"
    assert result.error_message is not None
    assert "input:" in result.error_message
    assert "topic: release" in result.error_message


def test_named_workflow_prefers_workflow_file_over_role_directory(initialized_project: Path, monkeypatch):
    workflow_dir = initialized_project / ".myteam" / "child"
    workflow_dir.mkdir()
    (workflow_dir / "role.md").write_text("Child role\n", encoding="utf-8")
    (workflow_dir / "load.py").write_text("print('role')\n", encoding="utf-8")

    workflow_file = initialized_project / ".myteam" / "child.py"
    workflow_file.write_text(
        "def main():\n"
        "    return {'answer': 'file'}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(initialized_project)

    result = run_named_workflow("child")

    assert result.status == "completed"
    assert result.output == {"answer": "file"}


def test_run_agent_returns_structured_failure_for_unexpected_exception(initialized_project: Path, monkeypatch):
    def boom(self, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("myteam.workflow.execution.steps.AgentContext._prepare_step", boom)

    result = run_agent(prompt="Say hello", cwd=initialized_project)

    assert result.status == "failed"
    assert result.error_type == "unexpected_error"
    assert "boom" in (result.error_message or "")
