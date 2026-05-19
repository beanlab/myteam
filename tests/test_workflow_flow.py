from __future__ import annotations

import sys
from pathlib import Path


def test_start_ignores_yaml_workflow_files(run_myteam_inprocess, initialized_project: Path):
    workflow_file = initialized_project / ".myteam" / "demo.yaml"
    workflow_file.write_text(
        "step1:\n"
        "  prompt: hello\n"
        "  output:\n"
        "    message: hi\n",
        encoding="utf-8",
    )

    result = run_myteam_inprocess(initialized_project, "start", "demo")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Workflow 'demo' not found." in result.stderr


def test_start_fails_when_workflow_file_is_missing(run_myteam_inprocess, initialized_project: Path):
    result = run_myteam_inprocess(initialized_project, "start", "missing")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Workflow 'missing' not found." in result.stderr


def test_start_accepts_prefix_for_workflow_lookup(run_myteam, tmp_path: Path):
    workflow_root = tmp_path / ".agents"
    workflow_root.mkdir()
    workflow_file = workflow_root / "demo.py"
    workflow_file.write_text(
        "from pathlib import Path\n"
        "Path('workflow_ran.txt').write_text('ok', encoding='utf-8')\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "start", "demo", "--prefix", ".agents")

    assert result.exit_code == 0
    assert result.stdout == ""
    assert result.stderr == ""
    assert (workflow_root / "workflow_ran.txt").read_text(encoding="utf-8") == "ok"


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


def test_start_verbose_logs_to_stderr(run_myteam_inprocess, initialized_project: Path):
    workflow_file = initialized_project / ".myteam" / "demo.py"
    workflow_file.write_text("VALUE = 1\n", encoding="utf-8")

    result = run_myteam_inprocess(initialized_project, "start", "demo", "--verbose")

    assert result.exit_code == 0
    assert result.stdout == ""
    assert "Resolved workflow 'demo' to" in result.stderr
    assert "Workflow 'demo' completed successfully." in result.stderr
