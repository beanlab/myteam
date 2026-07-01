"""Implementation-level tests for supervisor PTY workflow handling.

The governing testing philosophy permits lower-level coverage for PTY/session
handoff because failures are race-prone and difficult to diagnose only through
CLI assertions.
"""
from __future__ import annotations

import sys
from pathlib import Path

from myteam.workflows.execution.supervisor import Supervisor


def run_workflow(workflow: Path, cwd: Path) -> dict:
    with Supervisor() as supervisor:
        request_id = supervisor.start_top_level_workflow(
            argv=[sys.executable, str(workflow)],
            cwd=str(cwd),
            input_json=None,
        )
        result = supervisor.run_until_complete(request_id)
    assert result is not None
    return result


def test_workflow_runs_with_tty_stdin_and_stdout(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.py"
    workflow.write_text(
        "import sys\n"
        "from myteam.workflows import report_workflow_result\n"
        "report_workflow_result(f'stdin={sys.stdin.isatty()} stdout={sys.stdout.isatty()} stderr={sys.stderr.isatty()}')\n",
        encoding="utf-8",
    )

    result = run_workflow(workflow, tmp_path)

    assert result["status"] == "ok"
    assert result["result"]["exit_code"] == 0
    assert "stdin=True stdout=True" in result["result"]["result_text"]
    assert "transcript" not in result["result"]


def test_nested_start_runs_child_and_resumes_parent(tmp_path: Path) -> None:
    child = tmp_path / "child.py"
    child.write_text(
        "from myteam.workflows import report_workflow_result\n"
        "print('child live output')\n"
        "report_workflow_result('child result')\n",
        encoding="utf-8",
    )
    parent = tmp_path / "parent.py"
    parent.write_text(
        "from myteam.workflows.commands import start_workflow_cli\n"
        "from myteam.workflows import report_workflow_result\n"
        "print('parent before')\n"
        "start_workflow_cli('child.py')\n"
        "print('parent after')\n"
        "report_workflow_result('parent result')\n",
        encoding="utf-8",
    )

    result = run_workflow(parent, tmp_path)

    assert result["status"] == "ok"
    assert result["result"]["exit_code"] == 0
    assert result["result"]["result_text"] == "parent result\n"
    assert "transcript" not in result["result"]
