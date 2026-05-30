from __future__ import annotations

from pathlib import Path

from myteam import list_skills, list_tasks


def test_list_skills_returns_directory_names(monkeypatch, capsys, initialized_project: Path):
    root = initialized_project / ".myteam"
    skill_dir = root / "developer"
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.md").write_text(
        "---\n"
        "name: developer\n"
        "description: Handles project implementation work\n"
        "---\n"
        "Skill prompt\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("MYTEAM_PROJECT_ROOT", str(root))
    monkeypatch.setattr("myteam.disclosure.has_builtin_skill", lambda *_: False)

    result = list_skills()

    assert result == ["developer"]
    assert capsys.readouterr().out == ""


def test_get_skills_lists_child_skills_with_metadata(run_myteam, initialized_project: Path):
    skill_dir = initialized_project / ".myteam" / "developer"
    skill_dir.mkdir()
    (skill_dir / "skill.md").write_text(
        "---\n"
        "name: developer\n"
        "description: Handles project implementation work\n"
        "---\n"
        "Skill prompt\n",
        encoding="utf-8",
    )

    result = run_myteam(initialized_project, "get_skills")

    assert result.exit_code == 0
    assert "developer" in result.stdout
    assert "Handles project implementation work" in result.stdout


def test_list_tasks_returns_filenames(monkeypatch, capsys, initialized_project: Path):
    root = initialized_project / ".myteam"
    task_dir = root / "research"
    nested_dir = task_dir / "nested"
    task_dir.mkdir(parents=True)
    nested_dir.mkdir()
    (task_dir / "summary.md").write_text(
        "---\n"
        "name: research/summary\n"
        "description: Summarize the current state of the project\n"
        "input:\n"
        "  topic: implementation\n"
        "  audience: team\n"
        "---\n"
        "Task prompt\n",
        encoding="utf-8",
    )
    (nested_dir / "ignored.md").write_text(
        "---\n"
        "name: research/nested/ignored\n"
        "description: Ignore me\n"
        "---\n"
        "Nested prompt\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("MYTEAM_PROJECT_ROOT", str(root))

    result = list_tasks("research")

    assert result == ["research/summary.md"]
    assert capsys.readouterr().out == ""


def test_get_tasks_lists_tasks_and_input(run_myteam, initialized_project: Path):
    task_dir = initialized_project / ".myteam" / "research"
    task_dir.mkdir()
    (task_dir / "summary.md").write_text(
        "---\n"
        "name: research/summary\n"
        "description: Summarize the current state of the project\n"
        "input:\n"
        "  topic: implementation\n"
        "  audience: team\n"
        "---\n"
        "Task prompt\n",
        encoding="utf-8",
    )

    result = run_myteam(initialized_project, "get_tasks", "research")

    assert result.exit_code == 0
    assert "research/summary" in result.stdout
    assert "Summarize the current state of the project" in result.stdout
    assert "input:" in result.stdout
    assert "topic: implementation" in result.stdout
    assert "audience: team" in result.stdout


def test_get_tasks_lists_supported_workflow_files(run_myteam, initialized_project: Path):
    task_dir = initialized_project / ".myteam" / "workflows"
    task_dir.mkdir()
    (task_dir / "daily.py").write_text("print('daily')\n", encoding="utf-8")
    (task_dir / "summary.yaml").write_text("step1: {}\n", encoding="utf-8")
    (task_dir / "notes.yml").write_text("step1: {}\n", encoding="utf-8")

    result = run_myteam(initialized_project, "get_tasks", "workflows")

    assert result.exit_code == 0
    assert "workflows/daily.py" in result.stdout
    assert "workflows/summary.yaml" in result.stdout
    assert "workflows/notes.yml" in result.stdout


def test_get_task_prints_task_detail(run_myteam, initialized_project: Path):
    task_dir = initialized_project / ".myteam" / "research"
    task_dir.mkdir()
    task_file = task_dir / "summary.md"
    task_file.write_text(
        "---\n"
        "name: research/summary\n"
        "description: Summarize the current state of the project\n"
        "input:\n"
        "  topic: implementation\n"
        "---\n"
        "Task prompt\n",
        encoding="utf-8",
    )

    result = run_myteam(initialized_project, "get", "task", "research/summary")

    assert result.exit_code == 0
    assert "Summarize the current state of the project" in result.stdout
    assert "input:" in result.stdout
    assert "topic: implementation" in result.stdout
    assert "Task prompt" in result.stdout


def test_get_task_accepts_supported_workflow_files(run_myteam, initialized_project: Path):
    task_dir = initialized_project / ".myteam" / "workflows"
    task_dir.mkdir()
    task_file = task_dir / "daily.py"
    task_file.write_text("print('daily task')\n", encoding="utf-8")

    result = run_myteam(initialized_project, "get", "task", "workflows/daily")

    assert result.exit_code == 0
    assert "print('daily task')" in result.stdout
