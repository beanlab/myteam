from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

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
    monkeypatch.setattr(rosters, "_fetch_available_rosters", lambda _repo_url, _ref="main": [{"path": "starter", "type": "tree", "sha": "abc"}])
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
    managed_root = initialized_project / ".myteam" / "starter"
    assert (managed_root / "role.md").exists()
    assert (managed_root / "nested" / "skill.md").exists()
    metadata = yaml.safe_load((managed_root / ".source.yml").read_text(encoding="utf-8"))
    assert metadata["repo"] == rosters.DEFAULT_REPO
    assert metadata["roster"] == "starter"
    assert downloaded


def test_download_tree_roster_writes_to_explicit_destination(
    run_myteam_inprocess,
    initialized_project: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(rosters, "_fetch_available_rosters", lambda _repo_url, _ref="main": [{"path": "skills/foo", "type": "tree", "sha": "abc"}])
    monkeypatch.setattr(
        rosters,
        "_fetch_json",
        lambda url: {"tree": [{"path": "skill.md", "type": "blob"}, {"path": "helpers/load.py", "type": "blob"}]}
        if "abc" in url
        else {"tree": [{"path": "skills/foo", "type": "tree", "sha": "abc"}]},
    )

    def fake_download(url: str, output_path: Path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"downloaded from {url}\n", encoding="utf-8")

    monkeypatch.setattr(rosters, "_download_file", fake_download)

    result = run_myteam_inprocess(initialized_project, "download", "skills/foo", "bar/baz")

    assert result.exit_code == 0
    managed_root = initialized_project / ".myteam" / "bar" / "baz"
    assert (managed_root / "skill.md").exists()
    assert (managed_root / "helpers" / "load.py").exists()
    metadata = yaml.safe_load((managed_root / ".source.yml").read_text(encoding="utf-8"))
    assert metadata["roster"] == "skills/foo"
    assert metadata["local_path"] == ".myteam/bar/baz"


def test_download_single_file_roster_fails(run_myteam_inprocess, initialized_project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(rosters, "_fetch_available_rosters", lambda _repo_url, _ref="main": [{"path": "starter.md", "type": "blob"}])

    result = run_myteam_inprocess(initialized_project, "download", "starter.md")

    assert result.exit_code == 1
    assert "folder rosters are supported" in result.stderr


def test_download_existing_same_source_directs_user_to_update(
    run_myteam_inprocess,
    initialized_project: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    managed_root = initialized_project / ".myteam" / "starter"
    managed_root.mkdir(parents=True)
    (managed_root / ".source.yml").write_text("repo: beanlab/rosters\nroster: starter\n", encoding="utf-8")
    monkeypatch.setattr(rosters, "_fetch_available_rosters", lambda _repo_url, _ref="main": [{"path": "starter", "type": "tree", "sha": "abc"}])

    result = run_myteam_inprocess(initialized_project, "download", "starter")

    assert result.exit_code == 1
    assert "myteam update .myteam/starter" in result.stderr


def test_download_existing_unrelated_destination_fails_clearly(
    run_myteam_inprocess,
    initialized_project: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    managed_root = initialized_project / ".myteam" / "starter"
    managed_root.mkdir(parents=True)
    (managed_root / "role.md").write_text("local content\n", encoding="utf-8")
    monkeypatch.setattr(rosters, "_fetch_available_rosters", lambda _repo_url, _ref="main": [{"path": "starter", "type": "tree", "sha": "abc"}])

    result = run_myteam_inprocess(initialized_project, "download", "starter")

    assert result.exit_code == 1
    assert "delete it or choose a different destination" in result.stderr


def test_download_missing_roster_fails_with_available_names(run_myteam_inprocess, initialized_project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        rosters,
        "_fetch_available_rosters",
        lambda _repo_url, _ref="main": [{"path": "starter", "type": "tree"}, {"path": "other", "type": "tree"}],
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


def test_update_tree_roster_refreshes_files_and_metadata(
    run_myteam_inprocess,
    initialized_project: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    managed_root = initialized_project / ".myteam" / "starter"
    managed_root.mkdir(parents=True)
    (managed_root / "role.md").write_text("old content\n", encoding="utf-8")
    (managed_root / ".source.yml").write_text(
        yaml.safe_dump(
            {
                "repo": "beanlab/rosters",
                "roster": "starter",
                "ref": "main",
                "downloaded_at": "2020-01-01T00:00:00+00:00",
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(rosters, "_fetch_available_rosters", lambda _repo_url, _ref="main": [{"path": "starter", "type": "tree", "sha": "abc"}])
    monkeypatch.setattr(
        rosters,
        "_fetch_json",
        lambda url: {"tree": [{"path": "role.md", "type": "blob"}]}
        if "abc" in url
        else {"tree": [{"path": "starter", "type": "tree", "sha": "abc"}]},
    )

    def fake_download(url: str, output_path: Path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"downloaded from {url}\n", encoding="utf-8")

    monkeypatch.setattr(rosters, "_download_file", fake_download)

    result = run_myteam_inprocess(initialized_project, "update", "starter")

    assert result.exit_code == 0
    assert (managed_root / "role.md").read_text(encoding="utf-8") == (
        "downloaded from https://raw.githubusercontent.com/beanlab/rosters/main/starter/role.md\n"
    )
    metadata = yaml.safe_load((managed_root / ".source.yml").read_text(encoding="utf-8"))
    assert metadata["repo"] == "beanlab/rosters"
    assert metadata["roster"] == "starter"
    assert metadata["ref"] == "main"
    assert datetime.fromisoformat(metadata["downloaded_at"]).tzinfo == UTC


def test_update_accepts_explicit_agents_path(run_myteam_inprocess, initialized_project: Path, monkeypatch: pytest.MonkeyPatch):
    managed_root = initialized_project / ".myteam" / "starter"
    managed_root.mkdir(parents=True)
    (managed_root / ".source.yml").write_text("repo: beanlab/rosters\nroster: starter\nref: main\n", encoding="utf-8")
    monkeypatch.setattr(rosters, "_fetch_available_rosters", lambda _repo_url, _ref="main": [{"path": "starter", "type": "tree", "sha": "abc"}])
    monkeypatch.setattr(
        rosters,
        "_fetch_json",
        lambda url: {"tree": [{"path": "role.md", "type": "blob"}]}
        if "abc" in url
        else {"tree": [{"path": "starter", "type": "tree", "sha": "abc"}]},
    )

    def fake_download(_url: str, output_path: Path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("ok\n", encoding="utf-8")

    monkeypatch.setattr(rosters, "_download_file", fake_download)

    result = run_myteam_inprocess(initialized_project, "update", ".myteam/starter")

    assert result.exit_code == 0
    assert (managed_root / "role.md").read_text(encoding="utf-8") == "ok\n"


def test_update_without_path_refreshes_multiple_managed_subtrees(
    run_myteam_inprocess,
    initialized_project: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    first = initialized_project / ".myteam" / "starter"
    second = initialized_project / ".myteam" / "skills" / "foo"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (first / ".source.yml").write_text("repo: beanlab/rosters\nroster: starter\nref: main\n", encoding="utf-8")
    (second / ".source.yml").write_text("repo: beanlab/rosters\nroster: skills/foo\nref: main\n", encoding="utf-8")
    monkeypatch.setattr(
        rosters,
        "_fetch_available_rosters",
        lambda _repo_url, _ref="main": [
            {"path": "starter", "type": "tree", "sha": "abc"},
            {"path": "skills/foo", "type": "tree", "sha": "def"},
        ],
    )
    monkeypatch.setattr(
        rosters,
        "_fetch_json",
        lambda url: {"tree": [{"path": "role.md", "type": "blob"}]}
        if "abc" in url
        else {"tree": [{"path": "skill.md", "type": "blob"}]}
        if "def" in url
        else {
            "tree": [
                {"path": "starter", "type": "tree", "sha": "abc"},
                {"path": "skills/foo", "type": "tree", "sha": "def"},
            ]
        },
    )

    def fake_download(url: str, output_path: Path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"{output_path.name}:{url}\n", encoding="utf-8")

    monkeypatch.setattr(rosters, "_download_file", fake_download)

    result = run_myteam_inprocess(initialized_project, "update")

    assert result.exit_code == 0
    assert (first / "role.md").exists()
    assert (second / "skill.md").exists()


def test_update_missing_managed_target_fails(run_myteam_inprocess, initialized_project: Path):
    result = run_myteam_inprocess(initialized_project, "update", "starter")

    assert result.exit_code == 1
    assert "Managed download metadata not found" in result.stderr


def test_update_without_managed_downloads_fails(run_myteam_inprocess, initialized_project: Path):
    result = run_myteam_inprocess(initialized_project, "update")

    assert result.exit_code == 1
    assert "No managed downloads found" in result.stderr


def test_update_incomplete_metadata_fails(run_myteam_inprocess, initialized_project: Path):
    managed_root = initialized_project / ".myteam" / "starter"
    managed_root.mkdir(parents=True)
    (managed_root / ".source.yml").write_text("repo: beanlab/rosters\nroster: starter\n", encoding="utf-8")

    result = run_myteam_inprocess(initialized_project, "update", "starter")

    assert result.exit_code == 1
    assert "missing required fields: ref" in result.stderr
