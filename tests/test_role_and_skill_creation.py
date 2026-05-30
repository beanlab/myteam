from __future__ import annotations

from pathlib import Path

import yaml


def test_new_role_creates_definition_and_loader(run_myteam, initialized_project: Path):
    result = run_myteam(initialized_project, "new", "role", "developer")

    assert result.exit_code == 0
    role_file = initialized_project / ".myteam" / "developer" / "role.md"
    assert role_file.exists()
    assert (initialized_project / ".myteam" / "developer" / "load.py").exists()

    text = role_file.read_text(encoding="utf-8")
    frontmatter_text, _ = text.split("---\n", 2)[1:]
    frontmatter = yaml.safe_load(frontmatter_text)
    assert isinstance(frontmatter, dict)
    assert frontmatter["name"] == "developer"


def test_new_skill_supports_nested_paths(run_myteam, initialized_project: Path):
    result = run_myteam(initialized_project, "new", "skill", "python/testing")

    assert result.exit_code == 0
    skill_file = initialized_project / ".myteam" / "python" / "testing" / "skill.md"
    assert skill_file.exists()
    assert (initialized_project / ".myteam" / "python" / "testing" / "load.py").exists()

    text = skill_file.read_text(encoding="utf-8")
    frontmatter_text, _ = text.split("---\n", 2)[1:]
    frontmatter = yaml.safe_load(frontmatter_text)
    assert isinstance(frontmatter, dict)
    assert frontmatter["name"] == "python/testing"


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


def test_new_task_creates_python_task_script(run_myteam, initialized_project: Path):
    result = run_myteam(initialized_project, "new", "task", "agent.py")

    assert result.exit_code == 0
    assert (initialized_project / ".myteam" / "agent.py").exists()
    text = (initialized_project / ".myteam" / "agent.py").read_text(encoding="utf-8")
    assert "NotImplementedError" in text


def test_new_task_accepts_nested_python_paths(run_myteam, initialized_project: Path):
    result = run_myteam(initialized_project, "new", "task", "automation/daily.py")

    assert result.exit_code == 0
    assert (initialized_project / ".myteam" / "automation" / "daily.py").exists()


def test_new_task_creates_markdown_task(run_myteam, initialized_project: Path):
    result = run_myteam(initialized_project, "new", "task", "research/summary.md")

    task_file = initialized_project / ".myteam" / "research" / "summary.md"
    assert result.exit_code == 0
    assert task_file.exists()

    text = task_file.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    frontmatter_text, body = text.split("---\n", 2)[1:]
    frontmatter = yaml.safe_load(frontmatter_text)
    assert isinstance(frontmatter, dict)
    assert frontmatter["name"] == "research/summary"
    assert body.strip()


def test_new_task_creates_blank_yaml_task(run_myteam, initialized_project: Path):
    result = run_myteam(initialized_project, "new", "task", "ops/pipeline.yaml")

    task_file = initialized_project / ".myteam" / "ops" / "pipeline.yaml"
    assert result.exit_code == 0
    assert task_file.exists()
    assert task_file.read_text(encoding="utf-8") == ""


def test_new_task_creates_blank_yml_task(run_myteam, initialized_project: Path):
    result = run_myteam(initialized_project, "new", "task", "ops/pipeline.yml")

    task_file = initialized_project / ".myteam" / "ops" / "pipeline.yml"
    assert result.exit_code == 0
    assert task_file.exists()
    assert task_file.read_text(encoding="utf-8") == ""


def test_new_task_accepts_custom_prefix(run_myteam, tmp_path: Path):
    init_result = run_myteam(tmp_path, "init", "--prefix", ".agents")
    assert init_result.exit_code == 0

    result = run_myteam(tmp_path, "new", "task", "research/summary.md", "--prefix", ".agents")

    assert result.exit_code == 0
    assert (tmp_path / ".agents" / "research" / "summary.md").exists()


def test_new_task_requires_a_file_extension(run_myteam, initialized_project: Path):
    result = run_myteam(initialized_project, "new", "task", "research/summary")

    assert result.exit_code == 1
    assert "must include a file extension" in result.stderr


def test_new_task_rejects_unsupported_extension(run_myteam, initialized_project: Path):
    result = run_myteam(initialized_project, "new", "task", "research/summary.txt")

    assert result.exit_code == 1
    assert "unsupported extension" in result.stderr


def test_creating_existing_task_fails_clearly(run_myteam, initialized_project: Path):
    first = run_myteam(initialized_project, "new", "task", "research/summary.md")
    second = run_myteam(initialized_project, "new", "task", "research/summary.md")

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
