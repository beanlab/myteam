from __future__ import annotations

import os
from pathlib import Path

import pytest

from myteam.frontmatter import parse_python_frontmatter
from myteam.listing import list_resources
from myteam.skills import load_skill
from myteam.workflows.commands import new_workflow


def test_python_skill_inherits_calling_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    marker = tmp_path / "cwd-marker.txt"
    marker.write_text("called-from-project-root", encoding="utf-8")
    skill = skills_dir / "whereami.py"
    skill.write_text(
        '"""\n'
        'type: skill\n'
        'description: cwd check\n'
        '"""\n'
        "from pathlib import Path\n"
        "print(Path('cwd-marker.txt').read_text(encoding='utf-8'))\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert load_skill(str(skill)) == "called-from-project-root\n"


def test_listing_folder_header_omits_folder_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "agents" / "foo"
    folder.mkdir(parents=True)
    (folder / "description.md").write_text("List this folder for foo resources.\n", encoding="utf-8")
    (tmp_path / "agents" / "bar.md").write_text(
        "---\n"
        "type: skill\n"
        "description: bar skill\n"
        "---\n"
        "content\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    rendered = list_resources("agents")

    assert "----agents/foo/----\nList this folder for foo resources." in rendered
    assert "----folder: foo/----" not in rendered
    assert "----skill: agents/bar.md----\nbar skill" in rendered


def test_listing_missing_target_reports_filesystem_cause_and_exits_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as raised:
        list_resources("nonsense")

    captured = capsys.readouterr()
    assert raised.value.code == 1
    assert captured.out == ""
    assert "nonsense" in captured.err
    assert "No such file or directory" in captured.err
    assert "Not a skill folder" not in captured.err


def test_listing_symlink_loop_reports_stderr_and_exits_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "loop").symlink_to("loop")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as raised:
        list_resources("loop")

    captured = capsys.readouterr()
    assert raised.value.code == 1
    assert captured.out == ""
    assert "loop" in captured.err
    assert "Too many levels of symbolic links" in captured.err


def test_listing_deleted_cwd_reports_stderr_and_exits_one(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    previous_cwd = Path.cwd()
    deleted_cwd = tmp_path / "deleted-cwd"
    deleted_cwd.mkdir()
    os.chdir(deleted_cwd)
    deleted_cwd.rmdir()
    try:
        with pytest.raises(SystemExit) as raised:
            list_resources()
    finally:
        os.chdir(previous_cwd)

    captured = capsys.readouterr()
    assert raised.value.code == 1
    assert captured.out == ""
    assert "current directory" in captured.err
    assert "No such file or directory" in captured.err


def test_listing_file_target_is_interpreted_as_a_resource(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "file.md").write_text(
        "---\ntype: skill\ndescription: direct resource\n---\nbody\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert list_resources("file.md") == "----skill: file.md----\ndirect resource"


def test_new_python_workflow_template_has_documented_structure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    new_workflow("review.py")

    content = (tmp_path / "review.py").read_text(encoding="utf-8")
    frontmatter = parse_python_frontmatter(content)
    assert frontmatter["type"] == "workflow"
    assert "description" in frontmatter
    assert "usage" in frontmatter
    assert "run_agent" in content
    assert "report_workflow_result" in content
    assert "def main" in content
