from __future__ import annotations

from pathlib import Path


def test_remove_existing_role_directory(run_myteam, initialized_project: Path):
    run_myteam(initialized_project, "new", "role", "developer")

    result = run_myteam(initialized_project, "remove", "developer")

    assert result.exit_code == 0
    assert not (initialized_project / ".myteam" / "developer").exists()


def test_remove_existing_skill_directory(run_myteam, initialized_project: Path):
    run_myteam(initialized_project, "new", "skill", "python/testing")

    result = run_myteam(initialized_project, "remove", "python/testing")

    assert result.exit_code == 0
    assert not (initialized_project / ".myteam" / "python" / "testing").exists()


def test_remove_missing_path_fails(run_myteam, initialized_project: Path):
    result = run_myteam(initialized_project, "remove", "missing")

    assert result.exit_code == 1
    assert "not found" in result.stderr


def test_remove_non_directory_path_fails(run_myteam, initialized_project: Path):
    target = initialized_project / ".myteam" / "plain.txt"
    target.write_text("not a directory\n", encoding="utf-8")

    result = run_myteam(initialized_project, "remove", "plain.txt")

    assert result.exit_code == 1
    assert "is not a directory" in result.stderr
