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


def test_list_accepts_a_resource_file_target(run_myteam, tmp_path: Path) -> None:
    write_listing_fixture(tmp_path)

    result = run_myteam(tmp_path, "list", "agents/foo/bar.md")

    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout == "----skill: agents/foo/bar.md----\nbar skill"


def test_list_aggregates_multiple_targets_and_sorts_glob_style_argv_globally(run_myteam, tmp_path: Path) -> None:
    write_listing_fixture(tmp_path)

    result = run_myteam(
        tmp_path,
        "list",
        "agents/foo/yep.py",
        "agents/quux.md",
        "agents/foo/bar.md",
    )

    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout == (
        "----skill: agents/foo/bar.md----\n"
        "bar skill\n\n"
        "----workflow: agents/foo/yep.py----\n"
        "yep workflow\n\n"
        "----skill: agents/quux.md----\n"
        "quux skill"
    )


def test_list_directory_flag_selects_the_described_directory(run_myteam, tmp_path: Path) -> None:
    write_listing_fixture(tmp_path)

    short = run_myteam(tmp_path, "list", "-d", "agents/foo")
    long = run_myteam(tmp_path, "list", "--directory", "agents/foo")

    expected = "----agents/foo/----\nList foo when foo resources are relevant."
    for result in (short, long):
        assert result.exit_code == 0
        assert result.stderr == ""
        assert result.stdout == expected


def test_list_directory_flag_without_targets_selects_cwd(run_myteam, tmp_path: Path) -> None:
    (tmp_path / "description.md").write_text("Project resources.\n", encoding="utf-8")
    (tmp_path / "child.md").write_text(
        "---\ntype: skill\ndescription: must not be listed\n---\nbody\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "list", "-d")

    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout == "----./----\nProject resources."


def test_list_deduplicates_repeated_overlapping_and_symlink_aliased_targets(
    run_myteam, tmp_path: Path
) -> None:
    write_listing_fixture(tmp_path)
    (tmp_path / "bar-alias.md").symlink_to(tmp_path / "agents" / "foo" / "bar.md")

    result = run_myteam(
        tmp_path,
        "list",
        "agents/foo",
        "agents/foo/bar.md",
        "bar-alias.md",
        "agents/foo",
    )

    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout.count("bar skill") == 1
    assert result.stdout.count("baz skill") == 1
    assert result.stdout.count("yep workflow") == 1
    assert "----skill: agents/foo/bar.md----" in result.stdout
    assert "bar-alias.md" not in result.stdout


def test_list_ignores_non_resources_for_an_empty_success(run_myteam, tmp_path: Path) -> None:
    undescribed = tmp_path / "undescribed"
    undescribed.mkdir()
    (tmp_path / "notes.txt").write_text("unsupported\n", encoding="utf-8")
    (tmp_path / "malformed.md").write_text("not a resource\n", encoding="utf-8")

    result = run_myteam(
        tmp_path,
        "list",
        "notes.txt",
        "malformed.md",
        "-d",
        "undescribed",
    )

    assert result.exit_code == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_list_symlink_loop_reports_filesystem_error_without_output(run_myteam, tmp_path: Path) -> None:
    (tmp_path / "loop").symlink_to("loop")

    result = run_myteam(tmp_path, "list", "loop")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "loop" in result.stderr
    assert "Too many levels of symbolic links" in result.stderr


def test_list_filesystem_error_suppresses_partial_output_and_reports_cause_and_path(
    run_myteam, tmp_path: Path
) -> None:
    valid = tmp_path / "valid.md"
    valid.write_text("---\ntype: skill\ndescription: valid skill\n---\nbody\n", encoding="utf-8")

    result = run_myteam(tmp_path, "list", "valid.md", "missing.md")

    assert result.exit_code != 0
    assert result.stdout == ""
    assert "missing.md" in result.stderr
    assert "No such file or directory" in result.stderr
