from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from myteam import __version__


def test_version_reports_app_version(run_myteam, tmp_path: Path):
    result = run_myteam(tmp_path, "version")

    assert result.exit_code == 0
    assert result.stdout.strip() == f"myteam {__version__}"


def test_changelog_prints_packaged_changelog(run_myteam, tmp_path: Path):
    result = run_myteam(tmp_path, "changelog")

    assert result.exit_code == 0
    packaged_changelog = files("myteam").joinpath("CHANGELOG.md").read_text(encoding="utf-8")
    assert result.stdout.strip() == packaged_changelog.strip()
