from __future__ import annotations

import sys
from pathlib import Path

import pytest

from myteam.paths import workflow_candidates
from myteam.workflow.definition.models import WorkflowRunResult
from myteam.workflow.definition.models import StepResult


def test_start_runs_workflow_from_yaml_file(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    workflow_file = initialized_project / ".myteam" / "demo.yaml"
    workflow_file.write_text(
        "step1:\n"
        "  prompt: hello\n"
        "  output:\n"
        "    message: hi\n",
        encoding="utf-8",
    )

    seen: dict[str, object] = {}

    def fake_load_workflow(path: Path):
        seen["path"] = path
        return {"step1": {"prompt": "hello", "output": {"message": "hi"}}}

    def fake_run_workflow(workflow_definition, **kwargs):
        seen["workflow"] = workflow_definition
        seen["kwargs"] = kwargs
        return WorkflowRunResult(
            status="completed",
            output={
                "step1": {
                    "prompt": "hello",
                    "agent": "codex",
                    "output": {"message": "hi"},
                }
            },
        )

    monkeypatch.setattr("myteam.commands.load_workflow", fake_load_workflow)
    monkeypatch.setattr("myteam.commands.run_workflow", fake_run_workflow)

    result = run_myteam_inprocess(initialized_project, "start", "demo")

    assert result.exit_code == 0
    assert result.stdout == ""
    assert result.stderr == ""
    assert seen["path"] == workflow_file
    assert seen["workflow"] == {"step1": {"prompt": "hello", "output": {"message": "hi"}}}
    assert callable(seen["kwargs"]["logger"])


def test_start_accepts_prefix_for_workflow_lookup(run_myteam_inprocess, tmp_path: Path, monkeypatch):
    workflow_root = tmp_path / ".agents"
    workflow_root.mkdir()
    workflow_file = workflow_root / "demo.yaml"
    workflow_file.write_text(
        "step1:\n"
        "  prompt: hello\n"
        "  output:\n"
        "    message: hi\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("myteam.commands.load_workflow", lambda path: {"step1": {"prompt": "hello", "output": {"message": "hi"}}})
    monkeypatch.setattr(
        "myteam.commands.run_workflow",
        lambda workflow_definition, **kwargs: WorkflowRunResult(status="completed", output={}),
    )

    result = run_myteam_inprocess(tmp_path, "start", "demo", "--prefix", ".agents")

    assert result.exit_code == 0
    assert workflow_file.exists()


def test_start_accepts_yml_extension(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    workflow_file = initialized_project / ".myteam" / "demo.yml"
    workflow_file.write_text(
        "step1:\n"
        "  prompt: hello\n"
        "  output:\n"
        "    message: hi\n",
        encoding="utf-8",
    )

    seen: dict[str, Path] = {}

    def fake_load_workflow(path: Path):
        seen["path"] = path
        return {"step1": {"prompt": "hello", "output": {"message": "hi"}}}

    monkeypatch.setattr("myteam.commands.load_workflow", fake_load_workflow)
    monkeypatch.setattr(
        "myteam.commands.run_workflow",
        lambda workflow_definition, **kwargs: WorkflowRunResult(status="completed", output={}),
    )

    result = run_myteam_inprocess(initialized_project, "start", "demo")

    assert result.exit_code == 0
    assert seen["path"] == workflow_file


def test_workflow_candidates_prioritize_python_then_yaml_then_yml(initialized_project: Path):
    python_file = initialized_project / ".myteam" / "demo.py"
    markdown_file = initialized_project / ".myteam" / "demo.md"
    yaml_file = initialized_project / ".myteam" / "demo.yaml"
    yml_file = initialized_project / ".myteam" / "demo.yml"
    python_file.write_text("print('py')\n", encoding="utf-8")
    markdown_file.write_text("---\nname: Demo\n---\nTask prompt\n", encoding="utf-8")
    yaml_file.write_text("step1: {}\n", encoding="utf-8")
    yml_file.write_text("step1: {}\n", encoding="utf-8")

    assert workflow_candidates(initialized_project, "demo") == [python_file, markdown_file, yaml_file, yml_file]


def test_workflow_candidates_reject_unsupported_extension(initialized_project: Path):
    (initialized_project / ".myteam" / "demo.txt").write_text("ignored\n", encoding="utf-8")

    with pytest.raises(ValueError):
        workflow_candidates(initialized_project, "demo.txt")


def test_start_runs_python_workflow_file(run_myteam, initialized_project: Path):
    workflow_file = initialized_project / ".myteam" / "demo.py"
    workflow_file.write_text(
        "import os\n"
        "from pathlib import Path\n"
        "\n"
        "Path('workflow_ran.txt').write_text(\n"
        "    f\"cwd={Path.cwd()}\\nroot={os.environ.get('MYTEAM_PROJECT_ROOT')}\\n\",\n"
        "    encoding='utf-8',\n"
        ")\n",
        encoding="utf-8",
    )

    result = run_myteam(initialized_project, "start", "demo")

    assert result.exit_code == 0
    assert result.stdout == ""
    assert result.stderr == ""
    assert (initialized_project / ".myteam" / "workflow_ran.txt").read_text(encoding="utf-8") == (
        f"cwd={initialized_project / '.myteam'}\n"
        f"root={initialized_project / '.myteam'}\n"
    )


def test_start_passes_python_workflow_exit_code(run_myteam, initialized_project: Path):
    workflow_file = initialized_project / ".myteam" / "demo.py"
    workflow_file.write_text("raise SystemExit(7)\n", encoding="utf-8")

    result = run_myteam(initialized_project, "start", "demo")

    assert result.exit_code == 7
    assert result.stdout == ""
    assert result.stderr == ""


def test_start_runs_python_workflow_like_load_py(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    workflow_file = initialized_project / ".myteam" / "demo.py"
    workflow_file.write_text("VALUE = 1\n", encoding="utf-8")

    seen: dict[str, object] = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr("myteam.commands.subprocess.run", fake_run)

    result = run_myteam_inprocess(initialized_project, "start", "demo")

    assert result.exit_code == 0
    assert seen["args"] == [sys.executable, str(workflow_file)]
    assert seen["kwargs"]["cwd"] == workflow_file.parent
    assert seen["kwargs"]["check"] is False
    assert seen["kwargs"]["env"]["MYTEAM_PROJECT_ROOT"] == str(initialized_project / ".myteam")


def test_start_prefers_named_directory_over_workflow_files(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    workflow_dir = initialized_project / ".myteam" / "demo"
    workflow_dir.mkdir()
    (workflow_dir / "role.md").write_text("Demo role\n", encoding="utf-8")
    (workflow_dir / "load.py").write_text("print('role')\n", encoding="utf-8")
    (initialized_project / ".myteam" / "demo.py").write_text("print('py')\n", encoding="utf-8")
    (initialized_project / ".myteam" / "demo.yaml").write_text("step1: {}\n", encoding="utf-8")

    calls: list[tuple[str, Path]] = []

    monkeypatch.setattr(
        "myteam.commands._run_named_start_fallback",
        lambda **kwargs: calls.append(("named", kwargs["folder"])),
    )
    monkeypatch.setattr(
        "myteam.commands._run_python_start_workflow",
        lambda *args, **kwargs: calls.append(("py", args[0])),
    )
    monkeypatch.setattr(
        "myteam.commands._run_yaml_start_workflow",
        lambda *args, **kwargs: calls.append(("yaml", args[0])),
    )

    result = run_myteam_inprocess(initialized_project, "start", "demo")

    assert result.exit_code == 0
    assert calls == [("named", workflow_dir)]


def test_start_uses_explicit_python_file_when_directory_exists(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    workflow_dir = initialized_project / ".myteam" / "demo"
    workflow_dir.mkdir()
    (workflow_dir / "role.md").write_text("Demo role\n", encoding="utf-8")
    (workflow_dir / "load.py").write_text("print('role')\n", encoding="utf-8")
    python_file = initialized_project / ".myteam" / "demo.py"
    python_file.write_text("print('py')\n", encoding="utf-8")

    calls: list[tuple[str, Path]] = []

    monkeypatch.setattr(
        "myteam.commands._run_named_start_fallback",
        lambda **kwargs: calls.append(("named", kwargs["folder"])),
    )
    monkeypatch.setattr(
        "myteam.commands._run_python_start_workflow",
        lambda *args, **kwargs: calls.append(("py", args[0])),
    )
    monkeypatch.setattr(
        "myteam.commands._run_yaml_start_workflow",
        lambda *args, **kwargs: calls.append(("yaml", args[0])),
    )

    result = run_myteam_inprocess(initialized_project, "start", "demo.py")

    assert result.exit_code == 0
    assert calls == [("py", python_file)]
    assert result.stderr == ""


def test_start_prefers_python_workflow_when_multiple_files_exist(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    python_file = initialized_project / ".myteam" / "demo.py"
    yaml_file = initialized_project / ".myteam" / "demo.yaml"
    yml_file = initialized_project / ".myteam" / "demo.yml"
    python_file.write_text("print('py')\n", encoding="utf-8")
    yaml_file.write_text("step1: {}\n", encoding="utf-8")
    yml_file.write_text("step1: {}\n", encoding="utf-8")

    calls: list[tuple[str, Path]] = []

    monkeypatch.setattr(
        "myteam.commands._run_python_start_workflow",
        lambda *args, **kwargs: calls.append(("py", args[0])),
    )
    monkeypatch.setattr(
        "myteam.commands._run_yaml_start_workflow",
        lambda *args, **kwargs: calls.append(("yaml", args[0])),
    )
    monkeypatch.setattr(
        "myteam.commands._run_named_start_fallback",
        lambda **kwargs: calls.append(("named", kwargs["folder"])),
    )

    result = run_myteam_inprocess(initialized_project, "start", "demo")

    assert result.exit_code == 0
    assert calls == [("py", python_file)]
    assert result.stderr.strip() != ""


def test_start_runs_markdown_task_workflow(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    task_file = initialized_project / ".myteam" / "demo.md"
    task_file.write_text(
        "---\n"
        "name: Demo task\n"
        "description: Summarize notes\n"
        "agent: codex\n"
        "output:\n"
        "  result: short summary\n"
        "---\n"
        "Summarize the attached notes.\n",
        encoding="utf-8",
    )

    seen: dict[str, object] = {}

    def fake_run_default_workflow(prompt: str, **kwargs):
        seen["prompt"] = prompt
        seen["kwargs"] = kwargs
        return StepResult(status="completed", output={"result": "short summary"})

    monkeypatch.setattr("myteam.commands.run_default_workflow", fake_run_default_workflow)

    result = run_myteam_inprocess(initialized_project, "start", "demo.md")

    assert result.exit_code == 0
    assert result.stdout == ""
    assert result.stderr == ""
    assert seen["prompt"].strip()
    assert seen["kwargs"]["cwd"] == task_file.parent
    workflow_settings = seen["kwargs"]["workflow_settings"]
    assert workflow_settings.agent == "codex"
    assert workflow_settings.output == {"result": "short summary"}


def test_start_fails_when_workflow_file_is_missing(run_myteam_inprocess, initialized_project: Path):
    result = run_myteam_inprocess(initialized_project, "start", "missing")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.strip() != ""


def test_start_reports_workflow_parse_failures(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    workflow_file = initialized_project / ".myteam" / "demo.yaml"
    workflow_file.write_text("step1: {}\n", encoding="utf-8")

    def fake_load_workflow(path: Path):
        raise ValueError("bad workflow")

    monkeypatch.setattr("myteam.commands.load_workflow", fake_load_workflow)

    result = run_myteam_inprocess(initialized_project, "start", "demo")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Failed to load workflow 'demo': bad workflow" in result.stderr


def test_start_reports_failed_step_from_engine(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    workflow_file = initialized_project / ".myteam" / "demo.yaml"
    workflow_file.write_text(
        "step1:\n"
        "  prompt: hello\n"
        "  output:\n"
        "    message: hi\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("myteam.commands.load_workflow", lambda path: {"step1": {"prompt": "hello", "output": {"message": "hi"}}})
    monkeypatch.setattr(
        "myteam.commands.run_workflow",
        lambda workflow_definition, **kwargs: WorkflowRunResult(
            status="failed",
            failed_step_name="step1",
            error_message="missing completion",
        ),
    )

    result = run_myteam_inprocess(initialized_project, "start", "demo")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Workflow 'demo' failed at step 'step1': missing completion" in result.stderr


def test_start_verbose_logs_to_stderr(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    workflow_file = initialized_project / ".myteam" / "demo.yaml"
    workflow_file.write_text(
        "step1:\n"
        "  prompt: hello\n"
        "  output:\n"
        "    message: hi\n",
        encoding="utf-8",
    )

    def fake_load_workflow(path: Path):
        return {"step1": {"prompt": "hello", "output": {"message": "hi"}}}

    def fake_run_workflow(workflow_definition, **kwargs):
        logger = kwargs["logger"]
        assert logger is not None
        logger("Starting step 'step1'")
        logger("Completed step 'step1'")
        return WorkflowRunResult(status="completed", output={})

    monkeypatch.setattr("myteam.commands.load_workflow", fake_load_workflow)
    monkeypatch.setattr("myteam.commands.run_workflow", fake_run_workflow)

    result = run_myteam_inprocess(initialized_project, "start", "demo", "--verbose")

    assert result.exit_code == 0
    assert result.stdout == ""
    assert "Resolved workflow 'demo' to" in result.stderr
    assert "Loaded workflow with 1 step(s)" in result.stderr
    assert "Starting step 'step1'" in result.stderr
    assert "Completed step 'step1'" in result.stderr
    assert "Workflow 'demo' completed successfully." in result.stderr
