from __future__ import annotations

from pathlib import Path


def test_load_markdown_skill_prints_body_without_frontmatter(run_myteam, tmp_path: Path) -> None:
    skill = tmp_path / "skill.md"
    skill.write_text("---\ntype: skill\ndescription: demo\n---\n\nUse the skill.\n", encoding="utf-8")

    result = run_myteam(tmp_path, "load", "skill.md")

    assert result.exit_code == 0
    assert result.stdout == "\nUse the skill.\n"
    assert result.stderr == ""


def test_load_markdown_skill_renders_document_relative_jinja_helpers(run_myteam, tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "fragment.txt").write_text("# Rendered fragment\n", encoding="utf-8")
    skill = docs / "skill.md"
    skill.write_text(
        "---\n"
        "type: skill\n"
        "description: demo\n"
        "---\n"
        "{{ read_file('fragment.txt') | increase_headers(2) }}",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "load", "docs/skill.md")

    assert result.exit_code == 0
    assert result.stdout == "### Rendered fragment\n"
    assert result.stderr == ""


def test_load_markdown_skill_uses_configured_jinja_functions(
    run_myteam, tmp_path: Path, isolated_home: Path
) -> None:
    (isolated_home / "home_helpers.py").write_text(
        "def source():\n    return 'home'\n"
        "def shared():\n    return 'home shared'\n",
        encoding="utf-8",
    )
    (isolated_home / ".myteam.yaml").write_text(
        "jinja_functions:\n"
        "  source: home_helpers.py::source\n"
        "  shared: home_helpers.py::shared\n",
        encoding="utf-8",
    )
    helpers = tmp_path / "helpers"
    helpers.mkdir()
    (helpers / "jinja.py").write_text(
        "from pathlib import Path\n"
        "from jinja2 import pass_context\n"
        "marker = Path(__file__).with_name('imports.txt')\n"
        "marker.write_text((marker.read_text() if marker.exists() else '') + 'x')\n"
        "@pass_context\n"
        "def contextual(context, prefix):\n"
        "    return prefix + context['source']()\n"
        "def shared():\n"
        "    return 'project shared'\n"
        "def shell():\n"
        "    return 'custom shell'\n",
        encoding="utf-8",
    )
    (tmp_path / ".myteam.yaml").write_text(
        "jinja_functions:\n"
        "  contextual: helpers/jinja.py::contextual\n"
        "  shared: helpers/jinja.py::shared\n"
        "  shell: helpers/jinja.py::shell\n",
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "fragment.txt").write_text(
        "{{ contextual('included: ') }}", encoding="utf-8"
    )
    (docs / "skill.md").write_text(
        "---\ntype: skill\ndescription: demo\n---\n"
        "{{ source() }}|{{ shared() }}|{{ shell() }}|{{ read_file('fragment.txt') }}",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "load", "docs/skill.md")

    assert result.exit_code == 0
    assert result.stdout == "home|project shared|custom shell|included: home"
    assert result.stderr == ""
    assert (helpers / "imports.txt").read_text(encoding="utf-8") == "x"


def test_load_markdown_skill_rejects_noncallable_registered_function(
    run_myteam, tmp_path: Path
) -> None:
    (tmp_path / "helpers.py").write_text("not_a_function = 42\n", encoding="utf-8")
    (tmp_path / ".myteam.yaml").write_text(
        "jinja_functions:\n  helper: helpers.py::not_a_function\n", encoding="utf-8"
    )
    (tmp_path / "skill.md").write_text(
        "---\ntype: skill\ndescription: demo\n---\nliteral", encoding="utf-8"
    )

    result = run_myteam(tmp_path, "load", "skill.md")

    assert result.exit_code != 0
    assert result.stdout == ""
    assert "helper" in result.stderr
    assert "callable" in result.stderr


def test_load_markdown_skill_runs_shell_in_skill_directory(run_myteam, tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "shell-marker.txt").write_text("from skill shell\n", encoding="utf-8")
    skill = docs / "skill.md"
    skill.write_text(
        "---\ntype: skill\ndescription: demo\n---\n{{ shell('cat shell-marker.txt') }}",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "load", "docs/skill.md")

    assert result.exit_code == 0
    assert result.stdout == "from skill shell\n"
    assert result.stderr == ""


def test_load_markdown_skill_shell_failure_has_no_partial_rendered_output(
    run_myteam, tmp_path: Path
) -> None:
    command = "echo 'command stdout'; echo 'command stderr' >&2; exit 9"
    skill = tmp_path / "skill.md"
    skill.write_text(
        '---\ntype: skill\ndescription: demo\n---\nprefix {{ shell("' + command + '") }} suffix',
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "load", "skill.md")

    assert result.exit_code != 0
    assert result.stdout == ""
    assert command in result.stderr
    assert "9" in result.stderr
    assert "command stdout\ncommand stderr\n" in result.stderr


def test_load_markdown_skill_does_not_require_valid_frontmatter(run_myteam, tmp_path: Path) -> None:
    skill = tmp_path / "loose.md"
    skill.write_text("Just content.\n", encoding="utf-8")

    result = run_myteam(tmp_path, "load", "loose.md")

    assert result.exit_code == 0
    assert result.stdout == "Just content.\n"


def test_load_python_skill_uses_runtime_environment(run_myteam, tmp_path: Path, monkeypatch) -> None:
    skill = tmp_path / "skill.py"
    skill.write_text(
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "print(f'executable={Path(sys.executable).name}')\n"
        "print(f'cwd-marker={Path(\"cwd-marker.txt\").read_text(encoding=\"utf-8\").strip()}')\n"
        "print(f'env-marker={os.environ[\"MYTEAM_TEST_MARKER\"]}')\n"
        "print(f'argv-count={len(sys.argv)}')\n",
        encoding="utf-8",
    )
    (tmp_path / "cwd-marker.txt").write_text("from cwd\n", encoding="utf-8")
    monkeypatch.setenv("MYTEAM_TEST_MARKER", "from env")

    result = run_myteam(tmp_path, "load", "skill.py")

    assert result.exit_code == 0
    assert "executable=python" in result.stdout
    assert "cwd-marker=from cwd" in result.stdout
    assert "env-marker=from env" in result.stdout
    assert "argv-count=1" in result.stdout


def test_load_python_skill_failure_prints_stderr_and_omits_stdout(run_myteam, tmp_path: Path) -> None:
    skill = tmp_path / "broken.py"
    skill.write_text(
        "import sys\n"
        "print('hidden stdout')\n"
        "print('visible stderr', file=sys.stderr)\n"
        "sys.exit(7)\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "load", "broken.py")

    assert result.exit_code == 7
    assert "visible stderr" in result.stderr
    assert "hidden stdout" not in result.stdout


def test_load_folder_and_unsupported_extension_fail_clearly(run_myteam, tmp_path: Path) -> None:
    folder = tmp_path / "skills"
    folder.mkdir()
    unsupported = tmp_path / "skill.txt"
    unsupported.write_text("content\n", encoding="utf-8")

    folder_result = run_myteam(tmp_path, "load", "skills")
    unsupported_result = run_myteam(tmp_path, "load", "skill.txt")

    assert folder_result.exit_code == 1
    assert "Use 'myteam list skills'" in folder_result.stderr
    assert unsupported_result.exit_code == 1
    assert "unsupported extension" in unsupported_result.stderr
