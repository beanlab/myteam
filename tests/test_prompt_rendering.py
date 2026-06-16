from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import UndefinedError

import myteam.prompt_rendering as prompt_rendering


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


def test_render_markdown_body_recursively_renders_jinja_included_files(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "fragment.jinja").write_text("Hello {{ name }}", encoding="utf-8")

    rendered = prompt_rendering.render_markdown_body(
        "Start {{ read_file('fragment.jinja') }} End",
        source_path=docs / "skill.md",
        input_values={"name": "world"},
    )

    assert rendered == "Start Hello world End"


def test_render_markdown_body_resolves_nested_jinja_includes_relative_to_each_file(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    nested = docs / "parts"
    nested.mkdir(parents=True)
    (nested / "inner.jinja").write_text("INNER", encoding="utf-8")
    (nested / "outer.jinja").write_text("Outer: {{ read_file('inner.jinja') }}", encoding="utf-8")

    rendered = prompt_rendering.render_markdown_body(
        "{{ read_file('parts/outer.jinja') }}",
        source_path=docs / "skill.md",
        input_values={},
    )

    assert rendered == "Outer: INNER"


def test_render_markdown_body_rejects_recursive_include_cycles(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.jinja").write_text("A -> {{ read_file('b.jinja') }}", encoding="utf-8")
    (docs / "b.jinja").write_text("B -> {{ read_file('a.jinja') }}", encoding="utf-8")

    with pytest.raises(RuntimeError, match="cycle|recursive"):
        prompt_rendering.render_markdown_body(
            "{{ read_file('a.jinja') }}",
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

    def fake_list_resources(prefix: str | None = None) -> str:
        seen["prefix"] = prefix
        return "LIST"

    monkeypatch.setattr(prompt_rendering, "list_resources", fake_list_resources)

    rendered = prompt_rendering.render_markdown_body(
        "{{ myteam_explain() }}|{{ myteam_onboard() }}|{{ myteam_list('resources') }}",
        source_path=docs / "skill.md",
        input_values={},
    )

    assert rendered == "EXPLAIN|ONBOARD|LIST"
    assert Path(seen["prefix"]).resolve() == resources.resolve()


def test_render_markdown_body_prefers_input_values_over_helper_names(tmp_path: Path) -> None:
    source = tmp_path / "skill.md"

    rendered = prompt_rendering.render_markdown_body(
        "{{ read_file }}",
        source_path=source,
        input_values={"read_file": "shadowed"},
    )

    assert rendered == "shadowed"
