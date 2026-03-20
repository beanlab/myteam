from __future__ import annotations

from pathlib import Path

import pytest

from myteam import rosters


def test_list_prints_available_rosters(run_myteam_inprocess, initialized_project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        rosters,
        "_fetch_available_rosters",
        lambda _repo_url: [
            {"path": "starter", "type": "tree"},
            {"path": "single.md", "type": "blob"},
        ],
    )

    result = run_myteam_inprocess(initialized_project, "list")

    assert result.exit_code == 0
    assert "starter" in result.stdout
    assert "single.md" in result.stdout


def test_download_tree_roster_writes_files(run_myteam_inprocess, initialized_project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(rosters, "_fetch_available_rosters", lambda _repo_url: [{"path": "starter", "type": "tree", "sha": "abc"}])
    monkeypatch.setattr(
        rosters,
        "_fetch_json",
        lambda url: {"tree": [{"path": "role.md", "type": "blob"}, {"path": "nested/skill.md", "type": "blob"}]}
        if "abc" in url
        else {"tree": [{"path": "starter", "type": "tree", "sha": "abc"}]},
    )

    downloaded: list[tuple[str, Path]] = []

    def fake_download(url: str, output_path: Path):
        downloaded.append((url, output_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"downloaded from {url}\n", encoding="utf-8")

    monkeypatch.setattr(rosters, "_download_file", fake_download)

    result = run_myteam_inprocess(initialized_project, "download", "starter")

    assert result.exit_code == 0
    assert (initialized_project / ".myteam" / "role.md").exists()
    assert (initialized_project / ".myteam" / "nested" / "skill.md").exists()
    assert downloaded


def test_download_single_file_roster_writes_file(run_myteam_inprocess, initialized_project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(rosters, "_fetch_available_rosters", lambda _repo_url: [{"path": "starter.md", "type": "blob"}])

    def fake_download(url: str, output_path: Path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("single file\n", encoding="utf-8")

    monkeypatch.setattr(rosters, "_download_file", fake_download)

    result = run_myteam_inprocess(initialized_project, "download", "starter.md")

    assert result.exit_code == 0
    assert (initialized_project / ".myteam" / "starter.md").read_text(encoding="utf-8") == "single file\n"


def test_download_missing_roster_fails_with_available_names(run_myteam_inprocess, initialized_project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        rosters,
        "_fetch_available_rosters",
        lambda _repo_url: [{"path": "starter", "type": "tree"}, {"path": "other", "type": "tree"}],
    )

    result = run_myteam_inprocess(initialized_project, "download", "missing")

    assert result.exit_code == 1
    assert "Roster 'missing' not found." in result.stderr
    assert "starter" in result.stderr
    assert "other" in result.stderr


def test_list_invalid_repo_fails_clearly(run_myteam_inprocess, initialized_project: Path):
    result = run_myteam_inprocess(initialized_project, "list", "not-a-valid-repo")

    assert result.exit_code == 1
    assert "Invalid repo" in result.stderr
