from __future__ import annotations

import importlib.util
import locale
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

from jinja2 import Environment, StrictUndefined

from .commands import onboard
from .config import load_myteam_config
from .explain import explain_resources
from .listing import list_resources
from .markdown import increase_headers


def render_prompt_text(
    prompt: str,
    input_values: dict[str, Any] | None = None,
    *,
    source_path: Path | str | None = None,
    _include_stack: list[Path] | None = None,
    _jinja_functions: dict[str, Callable[..., Any]] | None = None,
) -> str:
    values = input_values or {}
    include_stack = [] if _include_stack is None else _include_stack
    jinja_functions = _load_configured_jinja_functions() if _jinja_functions is None else _jinja_functions
    environment = _build_environment(
        source_path=source_path,
        input_values=values,
        include_stack=include_stack,
        jinja_functions=jinja_functions,
    )
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
    jinja_functions: dict[str, Callable[..., Any]],
) -> Environment:
    environment = Environment(undefined=StrictUndefined)
    base_dir = _resolve_base_dir(source_path)
    builtins: dict[str, Any] = {
        "myteam_explain": explain_resources,
        "myteam_onboard": onboard,
        "myteam_list": _make_list_helper(base_dir),
        "myteam_load": _make_load_helper(base_dir),
        "increase_headers": increase_headers,
        "read_file": _make_read_file_helper(
            base_dir,
            input_values=input_values,
            include_stack=include_stack,
            jinja_functions=jinja_functions,
        ),
        "shell": _make_shell_helper(base_dir),
    }
    if source_path is not None:
        builtins["this_file"] = Path(source_path).resolve()
    environment.globals.update(builtins)
    environment.globals.update(jinja_functions)
    environment.filters["increase_headers"] = increase_headers
    return environment


def _load_configured_jinja_functions() -> dict[str, Callable[..., Any]]:
    config = load_myteam_config()
    if config is None:
        return {}

    modules: dict[Path, ModuleType] = {}
    functions: dict[str, Callable[..., Any]] = {}
    for name, target in config.jinja_functions.items():
        path_text, _, function_name = target.partition("::")
        path = Path(path_text.strip()).expanduser()
        function_name = function_name.strip()
        if not path.is_absolute():
            path = config._jinja_function_origins[name] / path
        path = path.resolve()

        module = modules.get(path)
        if module is None:
            module = _load_jinja_function_module(path)
            modules[path] = module

        function = getattr(module, function_name, None)
        if not callable(function):
            raise ValueError(
                f"Jinja function '{name}' target '{target}' does not identify a callable."
            )
        functions[name] = function

    return functions


def _load_jinja_function_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"_myteam_jinja_{abs(hash(path))}", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not load Jinja function module at {path}.")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise ValueError(f"Failed to load Jinja function module at {path}: {exc}") from exc
    return module


def _resolve_base_dir(source_path: Path | str | None) -> Path:
    if source_path is None:
        return Path.cwd().resolve()
    return Path(source_path).resolve().parent


def _make_shell_helper(base_dir: Path):
    def shell(command: str, timeout: float | None = None) -> str:
        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=base_dir,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            output = _normalize_timeout_output(error.stdout)
            raise RuntimeError(
                f"Shell command:\n{command}\nTimed out after {timeout!r} seconds. "
                f"Partial combined output:\n{output}"
            ) from error

        if completed.returncode != 0:
            raise RuntimeError(
                f"Shell command:\n{command}\nExited with code {completed.returncode}. "
                f"Combined output:\n{completed.stdout}"
            )
        return completed.stdout

    return shell


def _normalize_timeout_output(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode(locale.getpreferredencoding(False), errors="replace")
    return output


def _make_read_file_helper(
    base_dir: Path,
    *,
    input_values: dict[str, Any],
    include_stack: list[Path],
    jinja_functions: dict[str, Callable[..., Any]],
):
    def read_file(file: str | Path, render: bool = True) -> str:
        file_path = (base_dir / Path(file).expanduser()).resolve()
        if render:
            return _render_included_template(
                file_path,
                input_values=input_values,
                include_stack=include_stack,
                jinja_functions=jinja_functions,
            )
        return file_path.read_text(encoding="utf-8")

    return read_file


def _make_list_helper(base_dir: Path):
    def myteam_list(*paths: str | Path, directory: bool = False) -> str:
        requested = paths or (base_dir,)
        targets = tuple(base_dir / Path(path).expanduser() for path in requested)
        return list_resources(*targets, directory=directory)

    return myteam_list


def _make_load_helper(base_dir: Path):
    def myteam_load(skill: str | Path) -> str:
        from .skills import load_skill

        target = (base_dir / Path(skill).expanduser()).resolve()
        return load_skill(str(target))

    return myteam_load


def _render_included_template(
    file_path: Path,
    *,
    input_values: dict[str, Any],
    include_stack: list[Path],
    jinja_functions: dict[str, Callable[..., Any]],
) -> str:
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
            _jinja_functions=jinja_functions,
        )
    finally:
        include_stack.pop()
