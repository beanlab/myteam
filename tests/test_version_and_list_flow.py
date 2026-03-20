from __future__ import annotations

from pathlib import Path

from myteam import __version__


def test_version_reports_app_version(run_myteam, tmp_path: Path):
    result = run_myteam(tmp_path, "--version")

    assert result.exit_code == 0
    assert result.stdout.strip() == f"myteam {__version__}"
