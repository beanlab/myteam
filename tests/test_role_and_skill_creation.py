from __future__ import annotations

from pathlib import Path

import yaml


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


def test_new_role_accepts_custom_prefix(run_myteam, tmp_path: Path):
    init_result = run_myteam(tmp_path, "init", "--prefix", ".agents")
    assert init_result.exit_code == 0

    result = run_myteam(tmp_path, "new", "role", "developer", "--prefix", ".agents")

    assert result.exit_code == 0
    assert (tmp_path / ".agents" / "developer" / "role.md").exists()
    assert (tmp_path / ".agents" / "developer" / "load.py").exists()


def test_new_skill_accepts_custom_prefix(run_myteam, tmp_path: Path):
    init_result = run_myteam(tmp_path, "init", "--prefix", ".agents")
    assert init_result.exit_code == 0

    result = run_myteam(tmp_path, "new", "skill", "python/testing", "--prefix", ".agents")

    assert result.exit_code == 0
    assert (tmp_path / ".agents" / "python" / "testing" / "skill.md").exists()
    assert (tmp_path / ".agents" / "python" / "testing" / "load.py").exists()


def test_new_workflow_creates_default_agent_script(run_myteam, initialized_project: Path):
    result = run_myteam(initialized_project, "new", "workflow")

    assert result.exit_code == 0
    assert (initialized_project / ".myteam" / "agent.py").exists()


def test_new_workflow_accepts_nested_paths(run_myteam, initialized_project: Path):
    result = run_myteam(initialized_project, "new", "workflow", "automation/daily")

    assert result.exit_code == 0
    assert (initialized_project / ".myteam" / "automation" / "daily.py").exists()


def test_new_task_creates_markdown_workflow(run_myteam, initialized_project: Path):
    result = run_myteam(initialized_project, "new", "task", "research/summary")

    task_file = initialized_project / ".myteam" / "research" / "summary.md"
    assert result.exit_code == 0
    assert task_file.exists()

    text = task_file.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    frontmatter_text, body = text.split("---\n", 2)[1:]
    assert isinstance(yaml.safe_load(frontmatter_text), dict)
    assert body.strip()


def test_new_task_accepts_custom_prefix(run_myteam, tmp_path: Path):
    init_result = run_myteam(tmp_path, "init", "--prefix", ".agents")
    assert init_result.exit_code == 0

    result = run_myteam(tmp_path, "new", "task", "research/summary", "--prefix", ".agents")

    assert result.exit_code == 0
    assert (tmp_path / ".agents" / "research" / "summary.md").exists()


def test_creating_existing_workflow_fails_clearly(run_myteam, initialized_project: Path):
    first = run_myteam(initialized_project, "new", "workflow")
    second = run_myteam(initialized_project, "new", "workflow")

    assert first.exit_code == 0
    assert second.exit_code == 1
    assert "already exists" in second.stderr


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
