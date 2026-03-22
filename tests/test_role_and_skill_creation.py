from __future__ import annotations

from pathlib import Path


def test_new_role_creates_definition_and_loader(run_myteam, initialized_project: Path):
    result = run_myteam(initialized_project, "new", "role", "developer")

    assert result.exit_code == 0
    assert (initialized_project / ".myteam" / "developer" / "role.md").exists()
    assert (initialized_project / ".myteam" / "developer" / "load.py").exists()


def test_new_skill_supports_nested_paths(run_myteam, initialized_project: Path):
    result = run_myteam(initialized_project, "new", "skill", "python/testing")

    assert result.exit_code == 0
    assert (initialized_project / ".myteam" / "python" / "testing" / "skill.md").exists()
    assert (initialized_project / ".myteam" / "python" / "testing" / "load.py").exists()


def test_creating_existing_role_fails_clearly(run_myteam, initialized_project: Path):
    first = run_myteam(initialized_project, "new", "role", "developer")
    second = run_myteam(initialized_project, "new", "role", "developer")

    assert first.exit_code == 0
    assert second.exit_code == 1
    assert "already exists" in second.stderr


def test_creating_existing_skill_fails_clearly(run_myteam, initialized_project: Path):
    first = run_myteam(initialized_project, "new", "skill", "python")
    second = run_myteam(initialized_project, "new", "skill", "python")

    assert first.exit_code == 0
    assert second.exit_code == 1
    assert "already exists" in second.stderr


def test_creating_skill_in_reserved_builtin_namespace_fails_clearly(run_myteam, initialized_project: Path):
    result = run_myteam(initialized_project, "new", "skill", "builtins/changelog")

    assert result.exit_code == 1
    assert "reserved built-in namespace 'builtins'" in result.stderr
