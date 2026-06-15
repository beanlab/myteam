from __future__ import annotations

from pathlib import Path


def write_listing_fixture(root: Path) -> None:
    agents = root / "agents"
    foo = agents / "foo"
    hidden = agents / "hidden"
    foo.mkdir(parents=True)
    hidden.mkdir()
    (foo / "description.md").write_text("List foo when foo resources are relevant.\n", encoding="utf-8")
    (hidden / "bar.md").write_text("---\ntype: skill\ndescription: hidden skill\n---\nbody\n", encoding="utf-8")
    (foo / "bar.md").write_text("---\ntype: skill\ndescription: bar skill\n---\nbar body\n", encoding="utf-8")
    (foo / "baz.py").write_text(
        '"""\n'
        'type: skill\n'
        'description: baz skill\n'
        '"""\n'
        "raise RuntimeError('listing executed python file')\n",
        encoding="utf-8",
    )
    (foo / "yep.py").write_text(
        '"""\n'
        'type: workflow\n'
        'description: yep workflow\n'
        '"""\n'
        "raise RuntimeError('listing executed workflow')\n",
        encoding="utf-8",
    )
    (agents / "go.py").write_text(
        '"""\n'
        'type: workflow\n'
        'description: go workflow\n'
        '"""\n'
        "raise RuntimeError('listing executed python workflow')\n",
        encoding="utf-8",
    )
    (agents / "quux.md").write_text("---\ntype: skill\ndescription: quux skill\n---\nquux body\n", encoding="utf-8")
    (agents / "empty.md").write_text("---\ntype: skill\n---\nempty description body\n", encoding="utf-8")
    (agents / "nope.md").write_text("---\ndescription: missing type\n---\nignored\n", encoding="utf-8")
    (agents / "notes.txt").write_text("ignored\n", encoding="utf-8")


def test_list_displays_resources_under_prefix_without_executing_python_files(run_myteam, tmp_path: Path) -> None:
    write_listing_fixture(tmp_path)

    result = run_myteam(tmp_path, "list", "agents")

    assert result.exit_code == 0
    assert result.stderr == ""
    assert "----agents/foo/----\nList foo when foo resources are relevant." in result.stdout
    assert "----skill: agents/quux.md----\nquux skill" in result.stdout
    assert "----workflow: agents/go.py----\ngo workflow" in result.stdout
    assert "----skill: agents/empty.md----" in result.stdout
    assert "missing type" not in result.stdout
    assert "notes.txt" not in result.stdout
    assert "hidden" not in result.stdout
    assert "listing executed" not in result.stdout


def test_list_displays_nested_prefix_resources(run_myteam, tmp_path: Path) -> None:
    write_listing_fixture(tmp_path)

    result = run_myteam(tmp_path, "list", "agents/foo")

    assert result.exit_code == 0
    assert result.stdout == (
        "----skill: agents/foo/bar.md----\n"
        "bar skill\n\n"
        "----skill: agents/foo/baz.py----\n"
        "baz skill\n\n"
        "----workflow: agents/foo/yep.py----\n"
        "yep workflow"
    )


def test_list_default_prefix_uses_current_working_directory(run_myteam, tmp_path: Path) -> None:
    (tmp_path / "alpha.md").write_text("---\ntype: skill\ndescription: alpha skill\n---\nbody\n", encoding="utf-8")

    result = run_myteam(tmp_path, "list")

    assert result.exit_code == 0
    assert "----skill: alpha.md----\nalpha skill" in result.stdout


def test_list_missing_or_file_prefix_reports_not_a_skill_folder(run_myteam, tmp_path: Path) -> None:
    file_prefix = tmp_path / "file.md"
    file_prefix.write_text("not a folder\n", encoding="utf-8")

    missing = run_myteam(tmp_path, "list", "missing")
    file_result = run_myteam(tmp_path, "list", "file.md")

    assert missing.exit_code == 1
    assert "Not a skill folder:" in missing.stderr
    assert file_result.exit_code == 1
    assert "Not a skill folder:" in file_result.stderr
