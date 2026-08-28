from __future__ import annotations

from pathlib import Path
import shlex
import sys

import pytest
from jinja2 import UndefinedError

from myteam import list_resources
import myteam.prompt_rendering as prompt_rendering


def python_shell_command(script: str) -> str:
    return shlex.join([sys.executable, "-u", "-c", script])


def test_render_markdown_body_renders_inputs_and_control_flow(tmp_path: Path) -> None:
    source = tmp_path / "docs" / "skill.md"
    source.parent.mkdir()

    rendered = prompt_rendering.render_markdown_body(
        "{% if enabled %}Hello {{ name }}{% else %}Nope{% endif %}",
        source_path=source,
        input_values={"name": "world", "enabled": True},
    )

    assert rendered == "Hello world"


def test_render_markdown_body_raises_on_missing_variable(tmp_path: Path) -> None:
    source = tmp_path / "skill.md"

    with pytest.raises(UndefinedError):
        prompt_rendering.render_markdown_body(
            "Hello {{ missing }}",
            source_path=source,
            input_values={},
        )


def test_increase_headers_composes_with_includes_and_shell_output(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "fragment.txt").write_text(
        "{{ '# Included' | increase_headers }}", encoding="utf-8"
    )
    command = python_shell_command("print('# Shell')")
    template = (
        "{{ read_file('fragment.txt') | increase_headers(1) }}|"
        "{{ shell(command) | increase_headers(2) }}|"
        "{{ increase_headers(content, offset=2) }}|"
        "{{ content | increase_headers(2) }}"
    )

    rendered = prompt_rendering.render_markdown_body(
        template,
        source_path=docs / "skill.md",
        input_values={"command": command, "content": "# Direct"},
    )

    assert rendered == "### Included|### Shell\n|### Direct|### Direct"


def test_render_markdown_body_reads_files_relative_to_the_document(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "fragment.txt").write_text("from docs\n", encoding="utf-8")

    rendered = prompt_rendering.render_markdown_body(
        "{{ read_file('fragment.txt') }}",
        source_path=docs / "skill.md",
        input_values={},
    )

    assert rendered == "from docs\n"


def test_render_markdown_body_renders_included_files_by_default(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "fragment.txt").write_text("Hello {{ name }}", encoding="utf-8")

    rendered = prompt_rendering.render_markdown_body(
        "Start {{ read_file('fragment.txt') }} End",
        source_path=docs / "skill.md",
        input_values={"name": "world"},
    )

    assert rendered == "Start Hello world End"


def test_render_markdown_body_resolves_nested_includes_relative_to_each_file(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    nested = docs / "parts"
    nested.mkdir(parents=True)
    (nested / "inner.txt").write_text("INNER", encoding="utf-8")
    (nested / "outer.txt").write_text("Outer: {{ read_file('inner.txt') }}", encoding="utf-8")

    rendered = prompt_rendering.render_markdown_body(
        "{{ read_file('parts/outer.txt') }}",
        source_path=docs / "skill.md",
        input_values={},
    )

    assert rendered == "Outer: INNER"


def test_render_markdown_body_rejects_recursive_include_cycles(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("A -> {{ read_file('b.txt') }}", encoding="utf-8")
    (docs / "b.txt").write_text("B -> {{ read_file('a.txt') }}", encoding="utf-8")

    with pytest.raises(RuntimeError, match="cycle|recursive"):
        prompt_rendering.render_markdown_body(
            "{{ read_file('a.txt') }}",
            source_path=docs / "skill.md",
            input_values={},
        )


def test_render_markdown_body_exposes_helper_functions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    docs = tmp_path / "docs"
    resources = docs / "resources"
    resources.mkdir(parents=True)

    monkeypatch.setattr(prompt_rendering, "explain_resources", lambda: "EXPLAIN")
    monkeypatch.setattr(prompt_rendering, "onboard", lambda: "ONBOARD")

    seen: dict[str, object] = {}

    def fake_list_resources(*targets: str | Path, directory: bool = False) -> str:
        seen["targets"] = targets
        seen["directory"] = directory
        return "LIST"

    def fake_load_skill(skill: str) -> str:
        seen["skill"] = skill
        return "LOAD"

    monkeypatch.setattr(prompt_rendering, "list_resources", fake_list_resources)
    monkeypatch.setattr("myteam.skills.load_skill", fake_load_skill)

    rendered = prompt_rendering.render_markdown_body(
        "{{ myteam_explain() }}|{{ myteam_onboard() }}|"
        "{{ myteam_list('resources', 'other', directory=True) }}|{{ myteam_load('skills/demo.md') }}",
        source_path=docs / "skill.md",
        input_values={},
    )

    assert rendered == "EXPLAIN|ONBOARD|LIST|LOAD"
    assert tuple(Path(path).resolve() for path in seen["targets"]) == (
        resources.resolve(),
        (docs / "other").resolve(),
    )
    assert seen["directory"] is True
    assert Path(seen["skill"]).resolve() == (docs / "skills" / "demo.md").resolve()


def test_render_markdown_body_expands_home_paths_for_path_helpers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "fragment.txt").write_text("from home", encoding="utf-8")
    (home / "resources").mkdir()
    (home / "skills").mkdir()
    (home / "skills" / "demo.md").write_text("demo", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))

    seen: dict[str, object] = {}

    def fake_list_resources(*targets: str | Path, directory: bool = False) -> str:
        seen["targets"] = targets
        return "LIST"

    def fake_load_skill(skill: str) -> str:
        seen["skill"] = skill
        return "LOAD"

    monkeypatch.setattr(prompt_rendering, "list_resources", fake_list_resources)
    monkeypatch.setattr("myteam.skills.load_skill", fake_load_skill)

    rendered = prompt_rendering.render_markdown_body(
        "{{ read_file('~/fragment.txt') }}|{{ myteam_list('~/resources', 'local') }}|"
        "{{ myteam_load('~/skills/demo.md') }}",
        source_path=tmp_path / "docs" / "skill.md",
        input_values={},
    )

    assert rendered == "from home|LIST|LOAD"
    assert tuple(Path(path).resolve() for path in seen["targets"]) == (
        (home / "resources").resolve(),
        (tmp_path / "docs" / "local").resolve(),
    )
    assert Path(seen["skill"]).resolve() == (home / "skills" / "demo.md").resolve()


def test_myteam_list_without_paths_uses_the_document_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    seen: dict[str, object] = {}

    def fake_list_resources(*targets: str | Path, directory: bool = False) -> str:
        seen["targets"] = targets
        seen["directory"] = directory
        return "LIST"

    monkeypatch.setattr(prompt_rendering, "list_resources", fake_list_resources)

    rendered = prompt_rendering.render_markdown_body(
        "{{ myteam_list() }}",
        source_path=docs / "skill.md",
        input_values={},
    )

    assert rendered == "LIST"
    assert tuple(Path(path).resolve() for path in seen["targets"]) == (docs.resolve(),)
    assert seen["directory"] is False


def test_myteam_list_matches_enriched_python_api_and_cli(
    run_myteam, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "workflow.md").write_text(
        "---\n"
        "type: workflow\n"
        "description: Rendered listing\n"
        "input:\n"
        "  topic: subject\n"
        "output:\n"
        "  answer: response\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    rendered = prompt_rendering.render_markdown_body(
        "{{ myteam_list('workflow.md') }}",
        source_path=docs / "template.md",
        input_values={},
    )
    api = list_resources("docs/workflow.md")
    cli = run_myteam(tmp_path, "list", "docs/workflow.md")

    assert cli.exit_code == 0
    assert cli.stderr == ""
    assert rendered == api == cli.stdout
    assert "Usage:" in rendered
    assert "Input:" in rendered
    assert "Output:" in rendered


def test_myteam_list_metadata_failure_aborts_rendering_with_shared_error(
    run_myteam,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "invalid.md").write_text(
        "---\ntype: workflow\ndescription: invalid\ninput: scalar\n---\nbody\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    cli = run_myteam(tmp_path, "list", "docs/invalid.md")

    with pytest.raises(SystemExit) as raised:
        prompt_rendering.render_markdown_body(
            "literal prefix {{ myteam_list('invalid.md') }} literal suffix",
            source_path=docs / "template.md",
            input_values={},
        )

    captured = capsys.readouterr()
    assert raised.value.code == cli.exit_code == 1
    assert captured.out == cli.stdout == ""
    assert captured.err == cli.stderr
    assert "invalid.md" in captured.err
    assert "input" in captured.err
    assert "mapping" in captured.err.lower()


def test_myteam_list_symlink_loop_uses_listing_error_boundary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "loop").symlink_to("loop")

    with pytest.raises(SystemExit) as raised:
        prompt_rendering.render_markdown_body(
            "before {{ myteam_list('loop') }} after",
            source_path=docs / "skill.md",
            input_values={},
        )

    captured = capsys.readouterr()
    assert raised.value.code == 1
    assert captured.out == ""
    assert "loop" in captured.err
    assert "Too many levels of symbolic links" in captured.err


def test_myteam_list_system_exit_aborts_template_rendering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing_list_resources(*targets: str | Path, directory: bool = False) -> str:
        raise SystemExit(1)

    monkeypatch.setattr(prompt_rendering, "list_resources", failing_list_resources)

    with pytest.raises(SystemExit) as raised:
        prompt_rendering.render_markdown_body(
            "before {{ myteam_list('missing') }} after",
            source_path=tmp_path / "docs" / "skill.md",
            input_values={},
        )

    assert raised.value.code == 1


def test_render_markdown_body_can_opt_out_of_rendering_included_files(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "fragment.txt").write_text("Hello {{ name }}", encoding="utf-8")

    rendered = prompt_rendering.render_markdown_body(
        "Start {{ read_file('fragment.txt', render=False) }} End",
        source_path=docs / "skill.md",
        input_values={"name": "world"},
    )

    assert rendered == "Start Hello {{ name }} End"


def test_shell_returns_exact_combined_output_and_uses_source_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "cwd-marker.txt").write_text("from source", encoding="utf-8")
    monkeypatch.setenv("MYTEAM_SHELL_TEST", "from env")
    command = python_shell_command(
        "import os, pathlib, sys; "
        "sys.stdout.write('out\\n'); sys.stdout.flush(); "
        "sys.stderr.write('err\\n'); sys.stderr.flush(); "
        "print(os.environ['MYTEAM_SHELL_TEST']); "
        "print(pathlib.Path('cwd-marker.txt').read_text(), end='\\n'); "
        "print(sys.stdin.read() == '')"
    )

    rendered = prompt_rendering.render_markdown_body(
        "{{ shell(command) }}",
        source_path=docs / "skill.md",
        input_values={"command": command},
    )

    assert rendered == "out\nerr\nfrom env\nfrom source\nTrue\n"


def test_shell_preserves_empty_output(tmp_path: Path) -> None:
    rendered = prompt_rendering.render_markdown_body(
        "{{ shell(command) }}",
        source_path=tmp_path / "skill.md",
        input_values={"command": python_shell_command("pass")},
    )

    assert rendered == ""


def test_shell_without_source_path_uses_process_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "cwd-marker.txt").write_text("process cwd\n", encoding="utf-8")
    command = python_shell_command("from pathlib import Path; print(Path('cwd-marker.txt').read_text(), end='')")

    rendered = prompt_rendering.render_prompt_text("{{ shell(command) }}", {"command": command})

    assert rendered == "process cwd\n"


def test_shell_in_rendered_include_uses_included_file_directory(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    included = docs / "included"
    included.mkdir(parents=True)
    (included / "cwd-marker.txt").write_text("included cwd\n", encoding="utf-8")
    command = python_shell_command("from pathlib import Path; print(Path('cwd-marker.txt').read_text(), end='')")
    (included / "fragment.txt").write_text("{{ shell(command) }}", encoding="utf-8")

    rendered = prompt_rendering.render_markdown_body(
        "{{ read_file('included/fragment.txt') }}",
        source_path=docs / "skill.md",
        input_values={"command": command},
    )

    assert rendered == "included cwd\n"


def test_shell_nonzero_failure_reports_command_exit_code_and_combined_output(tmp_path: Path) -> None:
    command = python_shell_command(
        "import sys; print('failure stdout'); print('failure stderr', file=sys.stderr); sys.exit(7)"
    )

    with pytest.raises(Exception) as raised:
        prompt_rendering.render_markdown_body(
            "before {{ shell(command) }} after",
            source_path=tmp_path / "skill.md",
            input_values={"command": command},
        )

    diagnostic = str(raised.value)
    assert command in diagnostic
    assert "7" in diagnostic
    assert "failure stdout\nfailure stderr\n" in diagnostic


def test_shell_timeout_reports_command_timeout_and_partial_combined_output(tmp_path: Path) -> None:
    command = python_shell_command(
        "import sys, time; print('partial stdout', flush=True); "
        "print('partial stderr', file=sys.stderr, flush=True); time.sleep(0.5)"
    )

    with pytest.raises(Exception) as raised:
        prompt_rendering.render_markdown_body(
            "before {{ shell(command, timeout=0.05) }} after",
            source_path=tmp_path / "skill.md",
            input_values={"command": command},
        )

    diagnostic = str(raised.value)
    assert command in diagnostic
    assert "0.05" in diagnostic
    assert "partial stdout\npartial stderr\n" in diagnostic


def test_render_markdown_body_prefers_input_values_over_helper_names(tmp_path: Path) -> None:
    source = tmp_path / "skill.md"

    rendered = prompt_rendering.render_markdown_body(
        "{{ read_file }}|{{ shell }}|{{ increase_headers }}",
        source_path=source,
        input_values={
            "read_file": "shadowed read",
            "shell": "shadowed shell",
            "increase_headers": "shadowed headings",
        },
    )

    assert rendered == "shadowed read|shadowed shell|shadowed headings"
