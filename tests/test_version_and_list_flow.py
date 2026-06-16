from __future__ import annotations

from pathlib import Path

from myteam import __version__
from myteam.upgrade import packaged_changelog_text


def test_version_reports_app_version(run_myteam, tmp_path: Path):
    result = run_myteam(tmp_path, "version")

    assert result.exit_code == 0
    assert result.stdout.strip() == f"myteam {__version__}"


def test_changelog_prints_packaged_changelog(run_myteam, tmp_path: Path):
    result = run_myteam(tmp_path, "changelog")

    assert result.exit_code == 0
    assert result.stdout.strip() == packaged_changelog_text().strip()
