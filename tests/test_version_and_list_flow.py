from __future__ import annotations

from pathlib import Path

from myteam import __version__


def test_version_reports_app_version(run_myteam, tmp_path: Path):
    result = run_myteam(tmp_path, "--version")

    assert result.exit_code == 0
    assert result.stdout.strip() == f"myteam {__version__}"


def test_migrate_is_not_an_available_command(run_myteam, tmp_path: Path):
    result = run_myteam(tmp_path, "migrate")

    assert result.exit_code == 2
    assert "Cannot find key: migrate" in result.stderr
