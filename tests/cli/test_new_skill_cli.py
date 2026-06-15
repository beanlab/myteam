from __future__ import annotations

from pathlib import Path

import yaml


def markdown_frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    _, frontmatter_text, body = text.split("---\n", 2)
    return yaml.safe_load(frontmatter_text), body


def test_new_markdown_skill_creates_documented_template(run_myteam, tmp_path: Path) -> None:
    result = run_myteam(tmp_path, "new", "skill", "foo.md")

    skill = tmp_path / "foo.md"
    assert result.exit_code == 0
    assert skill.exists()
    frontmatter, body = markdown_frontmatter(skill)
    assert frontmatter["type"] == "skill"
    assert "description" in frontmatter
    assert "Not implemented yet" in body


def test_new_python_skill_creates_runnable_documented_template(run_myteam, tmp_path: Path) -> None:
    result = run_myteam(tmp_path, "new", "skill", "foo.py")

    skill = tmp_path / "foo.py"
    assert result.exit_code == 0
    text = skill.read_text(encoding="utf-8")
    assert "type: skill" in text
    assert "description:" in text
    assert "def main" in text
    assert "__main__" in text

    loaded = run_myteam(tmp_path, "load", "foo.py")
    assert loaded.exit_code == 0
    assert "Not implemented yet" in loaded.stdout


def test_new_skill_folder_creates_description_warning(run_myteam, tmp_path: Path) -> None:
    result = run_myteam(tmp_path, "new", "skill", "topic")

    description = tmp_path / "topic" / "description.md"
    assert result.exit_code == 0
    assert description.exists()
    assert "has not written a description" in description.read_text(encoding="utf-8")


def test_new_skill_parents_create_descriptions_without_overwriting_existing(run_myteam, tmp_path: Path) -> None:
    existing = tmp_path / "agents"
    existing.mkdir()
    existing_description = existing / "description.md"
    existing_description.write_text("Existing description.\n", encoding="utf-8")

    result = run_myteam(tmp_path, "new", "skill", "agents/foo/bar.md", "--parents")

    assert result.exit_code == 0
    assert (tmp_path / "agents" / "foo" / "bar.md").exists()
    assert existing_description.read_text(encoding="utf-8") == "Existing description.\n"
    assert (tmp_path / "agents" / "foo" / "description.md").exists()


def test_new_skill_existing_target_and_unsupported_extension_fail(run_myteam, tmp_path: Path) -> None:
    first = run_myteam(tmp_path, "new", "skill", "foo.md")
    second = run_myteam(tmp_path, "new", "skill", "foo.md")
    unsupported = run_myteam(tmp_path, "new", "skill", "foo.txt")

    assert first.exit_code == 0
    assert second.exit_code == 1
    assert "already exists" in second.stderr
    assert unsupported.exit_code == 1
    assert "unsupported extension" in unsupported.stderr
