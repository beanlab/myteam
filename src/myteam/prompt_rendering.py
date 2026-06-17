from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, StrictUndefined

from .commands import onboard
from .explain import explain_resources
from .listing import list_resources


def render_prompt_text(
    prompt: str,
    input_values: dict[str, Any] | None = None,
    *,
    source_path: Path | str | None = None,
    _include_stack: list[Path] | None = None,
) -> str:
    values = input_values or {}
    include_stack = [] if _include_stack is None else _include_stack
    environment = _build_environment(source_path=source_path, input_values=values, include_stack=include_stack)
    template = environment.from_string(prompt)
    rendered = template.render(**values)
    if prompt.endswith("\n") and not rendered.endswith("\n"):
        rendered += "\n"
    return rendered


def render_markdown_body(
    body: str,
    *,
    source_path: Path | str,
    input_values: dict[str, Any] | None = None,
) -> str:
    return render_prompt_text(body, input_values, source_path=source_path)


def _build_environment(
    *,
    source_path: Path | str | None,
    input_values: dict[str, Any],
    include_stack: list[Path],
) -> Environment:
    environment = Environment(undefined=StrictUndefined)
    base_dir = _resolve_base_dir(source_path)
    environment.globals.update(
        myteam_explain=explain_resources,
        myteam_onboard=onboard,
        myteam_list=_make_list_helper(base_dir),
        read_file=_make_read_file_helper(base_dir, input_values=input_values, include_stack=include_stack),
    )
    return environment


def _resolve_base_dir(source_path: Path | str | None) -> Path:
    if source_path is None:
        return Path.cwd().resolve()
    return Path(source_path).resolve().parent


def _make_read_file_helper(base_dir: Path, *, input_values: dict[str, Any], include_stack: list[Path]):
    def read_file(file: str | Path, render: bool = True) -> str:
        file_path = (base_dir / Path(file)).resolve()
        if render:
            return _render_included_template(file_path, input_values=input_values, include_stack=include_stack)
        return file_path.read_text(encoding="utf-8")

    return read_file


def _make_list_helper(base_dir: Path):
    def myteam_list(path: str | Path) -> str:
        target = (base_dir / Path(path)).resolve()
        return list_resources(str(target))

    return myteam_list


def _render_included_template(file_path: Path, *, input_values: dict[str, Any], include_stack: list[Path]) -> str:
    if file_path in include_stack:
        cycle = " -> ".join(str(path) for path in [*include_stack, file_path])
        raise RuntimeError(f"Recursive template include cycle detected: {cycle}")

    include_stack.append(file_path)
    try:
        return render_prompt_text(
            file_path.read_text(encoding="utf-8"),
            input_values,
            source_path=file_path,
            _include_stack=include_stack,
        )
    finally:
        include_stack.pop()
