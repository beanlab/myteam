from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from myteam.workflow.models import StepResult
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


def test_start_no_args_uses_root_load_py_prompt(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    root_load = initialized_project / ".myteam" / "load.py"
    root_load.write_text("print('ROOT PROMPT')\n", encoding="utf-8")

    seen: dict[str, object] = {}

    def fake_run_start_fallback(prompt: str, *, cwd: Path, workflow_settings):
        seen["prompt"] = prompt
        seen["cwd"] = cwd
        seen["workflow_settings"] = workflow_settings
        return StepResult(status="completed")

    monkeypatch.setattr("myteam.commands._run_start_fallback", fake_run_start_fallback)

    result = run_myteam_inprocess(initialized_project, "start")

    assert result.exit_code == 0
    assert result.stdout == ""
    assert seen["prompt"] == "ROOT PROMPT\n"
    assert seen["cwd"] == initialized_project / ".myteam"
    assert seen["workflow_settings"] is None


def test_start_and_get_role_share_loader_capture_helper(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    seen: dict[str, object] = {"calls": 0}

    def fake_run_load_py(dir_type: str, name_dir: Path, name: str | None, *, project_root: Path):
        seen["calls"] = int(seen["calls"]) + 1
        seen.setdefault("args", []).append((dir_type, name_dir, name, project_root))
        return subprocess.CompletedProcess(args=["python"], returncode=0, stdout="SHARED PROMPT\n", stderr="")

    def fake_run_start_fallback(prompt: str, *, cwd: Path, workflow_settings):
        seen["prompt"] = prompt
        seen["cwd"] = cwd
        seen["workflow_settings"] = workflow_settings
        return StepResult(status="completed")

    monkeypatch.setattr("myteam.commands._run_load_py", fake_run_load_py)
    monkeypatch.setattr("myteam.commands._run_start_fallback", fake_run_start_fallback)

    get_result = run_myteam_inprocess(initialized_project, "get", "role")
    assert get_result.exit_code == 0
    assert get_result.stdout == "SHARED PROMPT\n"

    start_result = run_myteam_inprocess(initialized_project, "start")
    assert start_result.exit_code == 0

    assert seen["calls"] == 2
    assert seen["prompt"] == "SHARED PROMPT\n"
    assert seen["cwd"] == initialized_project / ".myteam"


def test_start_uses_role_load_py_output_as_prompt(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    role_dir = initialized_project / ".myteam" / "developer"
    role_dir.mkdir()
    (role_dir / "role.md").write_text("Developer role\n", encoding="utf-8")
    (role_dir / "load.py").write_text("print('ROLE PROMPT')\n", encoding="utf-8")

    seen: dict[str, object] = {}

    def fake_run_start_fallback(prompt: str, *, cwd: Path, workflow_settings):
        seen["prompt"] = prompt
        seen["cwd"] = cwd
        seen["workflow_settings"] = workflow_settings
        return StepResult(status="completed")

    monkeypatch.setattr("myteam.commands._run_start_fallback", fake_run_start_fallback)

    result = run_myteam_inprocess(initialized_project, "start", "developer")

    assert result.exit_code == 0
    assert result.stdout == ""
    assert seen["prompt"] == "ROLE PROMPT\n"
    assert seen["cwd"] == role_dir
    assert seen["workflow_settings"] is None


def test_start_uses_skill_load_py_output_as_prompt(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    skill_dir = initialized_project / ".myteam" / "python"
    skill_dir.mkdir()
    (skill_dir / "skill.md").write_text("Python skill\n", encoding="utf-8")
    (skill_dir / "load.py").write_text("print('SKILL PROMPT')\n", encoding="utf-8")

    seen: dict[str, object] = {}

    def fake_run_start_fallback(prompt: str, *, cwd: Path, workflow_settings):
        seen["prompt"] = prompt
        seen["cwd"] = cwd
        seen["workflow_settings"] = workflow_settings
        return StepResult(status="completed")

    monkeypatch.setattr("myteam.commands._run_start_fallback", fake_run_start_fallback)

    result = run_myteam_inprocess(initialized_project, "start", "python")

    assert result.exit_code == 0
    assert result.stdout == ""
    assert seen["prompt"] == "SKILL PROMPT\n"
    assert seen["cwd"] == skill_dir
    assert seen["workflow_settings"] is None


def test_start_uses_role_frontmatter_workflow_settings(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    role_dir = initialized_project / ".myteam" / "review"
    role_dir.mkdir()
    (role_dir / "role.md").write_text(
        "---\n"
        "name: Review role\n"
        "workflow-settings:\n"
        "  agent: pi\n"
        "  input:\n"
        "    file: the file to review\n"
        "  output:\n"
        "    findings: list of findings\n"
        "  interactive: false\n"
        "  fork: false\n"
        "  usage_logging: verbose\n"
        "  inactivity_timeout_seconds: 900\n"
        "---\n\n"
        "Review {file}.\n",
        encoding="utf-8",
    )
    (role_dir / "load.py").write_text("print('PROMPT BODY')\n", encoding="utf-8")

    seen: dict[str, object] = {}

    def fake_run_start_fallback(prompt: str, *, cwd: Path, workflow_settings):
        seen["prompt"] = prompt
        seen["cwd"] = cwd
        seen["workflow_settings"] = workflow_settings
        return StepResult(status="completed")

    monkeypatch.setattr("myteam.commands._run_start_fallback", fake_run_start_fallback)

    result = run_myteam_inprocess(initialized_project, "start", "review")

    assert result.exit_code == 0
    assert seen["prompt"] == "PROMPT BODY\n"
    assert seen["cwd"] == role_dir
    assert seen["workflow_settings"].agent == "pi"
    assert seen["workflow_settings"].input == {"file": "the file to review"}
    assert seen["workflow_settings"].output == {"findings": "list of findings"}
    assert seen["workflow_settings"].interactive is False
    assert seen["workflow_settings"].fork is False
    assert seen["workflow_settings"].usage_logging == "verbose"
    assert seen["workflow_settings"].inactivity_timeout_seconds == 900


def test_start_formats_prompt_from_frontmatter_input(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    role_dir = initialized_project / ".myteam" / "formatter"
    role_dir.mkdir()
    (role_dir / "role.md").write_text(
        "---\n"
        "workflow-settings:\n"
        "  input:\n"
        "    file: review-notes.md\n"
        "---\n\n"
        "Please review {file}.\n",
        encoding="utf-8",
    )
    (role_dir / "load.py").write_text("print('Review {file}.')\n", encoding="utf-8")

    seen: dict[str, object] = {}

    def fake_run_start_fallback(prompt: str, *, cwd: Path, workflow_settings):
        seen["prompt"] = prompt
        seen["workflow_settings"] = workflow_settings
        return StepResult(status="completed")

    monkeypatch.setattr("myteam.commands._run_start_fallback", fake_run_start_fallback)

    result = run_myteam_inprocess(initialized_project, "start", "formatter")

    assert result.exit_code == 0
    assert seen["prompt"] == "Review review-notes.md.\n"
    assert seen["workflow_settings"].input == {"file": "review-notes.md"}


def test_start_fails_when_role_load_py_is_missing(run_myteam_inprocess, initialized_project: Path):
    role_dir = initialized_project / ".myteam" / "developer"
    role_dir.mkdir()
    (role_dir / "role.md").write_text("Developer role\n", encoding="utf-8")

    result = run_myteam_inprocess(initialized_project, "start", "developer")

    assert result.exit_code == 1
    assert "No load.py found for role 'developer'." in result.stderr


def test_start_reports_loader_failures(run_myteam, initialized_project: Path):
    role_dir = initialized_project / ".myteam" / "broken"
    role_dir.mkdir()
    (role_dir / "role.md").write_text("Broken role\n", encoding="utf-8")
    (role_dir / "load.py").write_text("raise RuntimeError('load failed')\n", encoding="utf-8")

    result = run_myteam(initialized_project, "start", "broken")

    assert result.exit_code == 1
    assert "RuntimeError: load failed" in result.stderr


def test_start_fails_on_malformed_frontmatter(run_myteam_inprocess, initialized_project: Path):
    role_dir = initialized_project / ".myteam" / "malformed"
    role_dir.mkdir()
    (role_dir / "role.md").write_text(
        "---\n"
        "workflow-settings:\n"
        "  input: [unterminated\n"
        "---\n\n"
        "Prompt body.\n",
        encoding="utf-8",
    )
    (role_dir / "load.py").write_text("print('PROMPT BODY')\n", encoding="utf-8")

    result = run_myteam_inprocess(initialized_project, "start", "malformed")

    assert result.exit_code == 1
    assert "Failed to load workflow settings for role 'malformed'" in result.stderr


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
