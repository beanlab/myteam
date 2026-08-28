from __future__ import annotations

from pathlib import Path
import shlex

import pytest


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


def test_list_enriches_workflows_and_preserves_skill_output(run_myteam, tmp_path: Path) -> None:
    (tmp_path / "skill.md").write_text(
        "---\ntype: skill\ndescription: unchanged skill\n---\nbody\n", encoding="utf-8"
    )
    (tmp_path / "python.py").write_text(
        '\"\"\"\n'
        "type: workflow\n"
        "description: Python workflow\n"
        "usage: |\n"
        "  \n"
        "  python.py --first VALUE\n"
        "    --continued\n"
        "  \n"
        '\"\"\"\n',
        encoding="utf-8",
    )
    (tmp_path / "markdown.md").write_text(
        "---\n"
        "type: workflow\n"
        "description: Markdown workflow\n"
        "usage: this authored value is ignored\n"
        "input:\n"
        "  topic: release notes\n"
        "  nested:\n"
        "    count: 2\n"
        "  items: []\n"
        "output:\n"
        "  summary: short text\n"
        "  details: {}\n"
        "---\nbody\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "list", "skill.md", "python.py", "markdown.md")

    placeholder = "<JSON matching Input>"
    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout == (
        "----workflow: markdown.md----\n"
        "Markdown workflow\n\n"
        "Usage:\n"
        f"myteam start markdown.md --input {shlex.quote(placeholder)}\n\n"
        "Input:\n"
        "topic: release notes\n"
        "nested:\n"
        "  count: 2\n"
        "items: []\n\n"
        "Output:\n"
        "summary: short text\n"
        "details: {}\n\n"
        "----workflow: python.py----\n"
        "Python workflow\n\n"
        "Usage:\n"
        "python.py --first VALUE\n"
        "  --continued\n\n"
        "----skill: skill.md----\n"
        "unchanged skill"
    )


def test_list_markdown_empty_input_quotes_actual_path_and_output_only_has_no_usage(
    run_myteam, tmp_path: Path
) -> None:
    workflows = tmp_path / "flows"
    workflows.mkdir()
    input_path = "flows/review it's $(safe).md"
    (tmp_path / input_path).write_text(
        "---\ntype: workflow\ndescription: Empty input\ninput: {}\noutput: null\n---\nbody\n",
        encoding="utf-8",
    )
    (workflows / "output-only.md").write_text(
        "---\n"
        "type: workflow\n"
        "description: Output only\n"
        "usage: must be ignored\n"
        "input: null\n"
        "output: {}\n"
        "---\nbody\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "list", input_path, "flows/output-only.md")

    placeholder = "<JSON matching Input>"
    command = f"myteam start {shlex.quote(input_path)} --input {shlex.quote(placeholder)}"
    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout == (
        "----workflow: flows/output-only.md----\n"
        "Output only\n\n"
        "Output:\n"
        "{}\n\n"
        f"----workflow: {input_path}----\n"
        "Empty input\n\n"
        "Usage:\n"
        f"{command}\n\n"
        "Input:\n"
        "{}"
    )
    assert shlex.split(command) == [
        "myteam",
        "start",
        input_path,
        "--input",
        placeholder,
    ]


def test_list_omits_unspecified_and_blank_python_usage(run_myteam, tmp_path: Path) -> None:
    for name, usage in (
        ("missing.py", "input: scalar\noutput: [still, ignored]\n"),
        ("null.py", "usage: null\n"),
        ("empty.py", "usage: ''\n"),
        ("blank.py", "usage: '   '\n"),
    ):
        (tmp_path / name).write_text(
            f'\"\"\"\ntype: workflow\ndescription: {name}\n{usage}\"\"\"\n',
            encoding="utf-8",
        )

    result = run_myteam(tmp_path, "list", "missing.py", "null.py", "empty.py", "blank.py")

    assert result.exit_code == 0
    assert result.stderr == ""
    assert "Usage:" not in result.stdout


@pytest.mark.parametrize(
    ("filename", "metadata", "field", "actual", "expected"),
    [
        ("workflow.py", "usage: 42", "usage", "int", "string"),
        ("workflow.md", "input: []", "input", "list", "mapping"),
        ("workflow.md", "output: false", "output", "bool", "mapping"),
    ],
)
def test_list_rejects_invalid_workflow_metadata_without_partial_stdout(
    run_myteam,
    tmp_path: Path,
    filename: str,
    metadata: str,
    field: str,
    actual: str,
    expected: str,
) -> None:
    (tmp_path / "valid.md").write_text(
        "---\ntype: skill\ndescription: must be suppressed\n---\nbody\n", encoding="utf-8"
    )
    delimit = '\"\"\"' if filename.endswith(".py") else "---"
    (tmp_path / filename).write_text(
        f"{delimit}\ntype: workflow\ndescription: invalid\n{metadata}\n{delimit}\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "list", "valid.md", filename)

    assert result.exit_code == 1
    assert result.stdout == ""
    assert filename in result.stderr
    assert field in result.stderr
    assert actual.lower() in result.stderr.lower()
    assert expected.lower() in result.stderr.lower()


def test_list_accepts_yaml_native_values_inside_markdown_schema_mappings(
    run_myteam, tmp_path: Path
) -> None:
    (tmp_path / "workflow.md").write_text(
        "---\n"
        "type: workflow\n"
        "description: YAML-native schema\n"
        "input:\n"
        "  1: numeric key\n"
        "  when: 2025-01-02\n"
        "  estimate: .nan\n"
        "output:\n"
        "  completed: 2025-01-03\n"
        "---\nbody\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "list", "workflow.md")

    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout == (
        "----workflow: workflow.md----\n"
        "YAML-native schema\n\n"
        "Usage:\n"
        "myteam start workflow.md --input '<JSON matching Input>'\n\n"
        "Input:\n"
        "1: numeric key\n"
        "when: 2025-01-02\n"
        "estimate: .nan\n\n"
        "Output:\n"
        "completed: 2025-01-03"
    )


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
