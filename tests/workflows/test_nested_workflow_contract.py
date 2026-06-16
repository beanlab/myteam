from __future__ import annotations

from pathlib import Path


def test_nested_start_returns_child_reported_result_to_parent_without_child_live_output(
    run_myteam,
    tmp_path: Path,
) -> None:
    child = tmp_path / "child.py"
    child.write_text(
        "from myteam.workflows import report_workflow_result\n"
        "print('child live display')\n"
        "report_workflow_result('child result')\n",
        encoding="utf-8",
    )
    parent = tmp_path / "parent.py"
    parent.write_text(
        "import subprocess\n"
        "import sys\n"
        "from myteam.workflows import report_workflow_result\n"
        "completed = subprocess.run(\n"
        "    [sys.executable, '-m', 'myteam', 'start', 'child.py'],\n"
        "    text=True,\n"
        "    capture_output=True,\n"
        "    check=False,\n"
        ")\n"
        "report_workflow_result(f'parent saw: {completed.stdout}', end='')\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "start", "parent.py")

    assert result.exit_code == 0
    assert result.stdout == "parent saw: child result\n"
    assert "child live display" not in result.stdout
    assert result.stderr == ""
