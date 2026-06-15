from __future__ import annotations

from pathlib import Path

import pytest

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


def test_listing_missing_prefix_reports_not_a_skill_folder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit):
        list_resources("nonsense")

    assert "Not a skill folder:" in capsys.readouterr().err


def test_listing_file_prefix_reports_not_a_skill_folder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "file.md").write_text("not a folder\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit):
        list_resources("file.md")

    assert "Not a skill folder:" in capsys.readouterr().err


def test_new_python_workflow_uses_packaged_template(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    new_workflow("review.py")

    content = (tmp_path / "review.py").read_text(encoding="utf-8")
    assert "type: workflow" in content
    assert "usage: no arguments" in content
    assert "from myteam import report_workflow_result, run_agent" in content
    assert 'report_workflow_result(json.dumps(result.output) + "\\n")' in content
    assert "to_jsonable" not in content
