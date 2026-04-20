from __future__ import annotations

from pathlib import Path

from myteam.workflow.models import WorkflowRunResult


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


def test_start_fails_when_workflow_file_is_missing(run_myteam_inprocess, initialized_project: Path):
    result = run_myteam_inprocess(initialized_project, "start", "missing")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Workflow 'missing' not found." in result.stderr


def test_start_fails_for_ambiguous_workflow_extensions(run_myteam_inprocess, initialized_project: Path):
    (initialized_project / ".myteam" / "demo.yaml").write_text("step1: {}\n", encoding="utf-8")
    (initialized_project / ".myteam" / "demo.yml").write_text("step1: {}\n", encoding="utf-8")

    result = run_myteam_inprocess(initialized_project, "start", "demo")

    assert result.exit_code == 1
    assert "Workflow 'demo' is ambiguous." in result.stderr


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
        lambda workflow_definition, **kwargs: WorkflowRunResult(status="failed", failed_step_name="step1"),
    )

    result = run_myteam_inprocess(initialized_project, "start", "demo")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Workflow 'demo' failed at step 'step1'." in result.stderr


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
