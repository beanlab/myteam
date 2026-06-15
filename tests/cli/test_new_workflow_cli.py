from __future__ import annotations

from pathlib import Path

import yaml


def markdown_frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    _, frontmatter_text, body = text.split("---\n", 2)
    return yaml.safe_load(frontmatter_text), body


def test_new_markdown_workflow_creates_documented_template(run_myteam, tmp_path: Path) -> None:
    result = run_myteam(tmp_path, "new", "workflow", "review.md")

    workflow = tmp_path / "review.md"
    assert result.exit_code == 0
    frontmatter, body = markdown_frontmatter(workflow)
    assert frontmatter["type"] == "workflow"
    assert "description" in frontmatter
    assert body.strip()


def test_new_python_workflow_creates_documented_template(run_myteam, tmp_path: Path) -> None:
    result = run_myteam(tmp_path, "new", "workflow", "review.py")

    workflow = tmp_path / "review.py"
    assert result.exit_code == 0
    text = workflow.read_text(encoding="utf-8")
    assert "type: workflow" in text
    assert "usage:" in text
    assert "run_agent" in text
    assert "report_workflow_result" in text
    assert "def main" in text


def test_new_workflow_parents_create_directories(run_myteam, tmp_path: Path) -> None:
    result = run_myteam(tmp_path, "new", "workflow", "agents/review.py", "--parents")

    assert result.exit_code == 0
    assert (tmp_path / "agents" / "review.py").exists()


def test_new_workflow_existing_missing_extension_and_unsupported_extension_fail(run_myteam, tmp_path: Path) -> None:
    first = run_myteam(tmp_path, "new", "workflow", "review.py")
    second = run_myteam(tmp_path, "new", "workflow", "review.py")
    no_extension = run_myteam(tmp_path, "new", "workflow", "review")
    unsupported = run_myteam(tmp_path, "new", "workflow", "review.txt")

    assert first.exit_code == 0
    assert second.exit_code == 1
    assert "already exists" in second.stderr
    assert no_extension.exit_code == 1
    assert "must end in .md or .py" in no_extension.stderr
    assert unsupported.exit_code == 1
    assert "unsupported extension" in unsupported.stderr
