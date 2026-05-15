from __future__ import annotations

import importlib
import importlib.util
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from .agent_utils import encode_input


@dataclass(frozen=True)
class AgentRuntimeConfig:
    name: str
    exec: str
    exit_sequence: bytes
    get_session_id: Callable[[str], str]
    build_argv: Callable[[str, str | None], list[str]]
    source: Path | str


class AgentConfigError(Exception):
    pass


def resolve_agent_runtime_config(
    name: str | None,
    *,
    project_root: Path | None = None,
    logger: Callable[[str], None] | None = None,
) -> AgentRuntimeConfig:
    agent_name = _require_agent_name(name)
    root = Path.cwd() if project_root is None else project_root
    local_path = root / ".myteam" / ".config" / f"{agent_name}.py"

    if local_path.exists():
        try:
            module = _load_module_from_path(agent_name, local_path)
            config = _config_from_module(agent_name, module, source=local_path)
        except Exception as exc:
            _log(
                logger,
                f"Local workflow agent config '{local_path}' is unusable: {exc}. "
                "Falling back to packaged default.",
            )
        else:
            _log(logger, f"Using local workflow agent config '{local_path}'.")
            return config
    else:
        _log(logger, f"Local workflow agent config '{local_path}' not found. Falling back to packaged default.")

    try:
        module = importlib.import_module(f"myteam.workflow.agents.{agent_name}")
        config = _config_from_module(
            agent_name,
            module,
            source=f"myteam.workflow.agents.{agent_name}",
        )
    except ModuleNotFoundError as exc:
        if exc.name == f"myteam.workflow.agents.{agent_name}":
            raise KeyError(f"Unknown workflow agent: {agent_name}") from exc
        raise
    except AgentConfigError as exc:
        raise KeyError(f"Invalid packaged workflow agent config for {agent_name}: {exc}") from exc

    _log(logger, f"Using packaged workflow agent config for '{agent_name}'.")
    return config


def _require_agent_name(name: str | None) -> str:
    if not name:
        raise KeyError("Unknown workflow agent: None")
    if not name.isidentifier():
        raise KeyError(f"Unknown workflow agent: {name}")
    return name


def _load_module_from_path(agent_name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"_myteam_workflow_agent_{agent_name}", path)
    if spec is None or spec.loader is None:
        raise AgentConfigError("could not create import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config_from_module(agent_name: str, module: ModuleType, *, source: Path | str) -> AgentRuntimeConfig:
    exec_name = _required_attr(module, "EXEC", str)
    exit_sequence = _exit_sequence_from_module(module)
    get_session_id = _required_callable(module, "get_session_id")
    build_argv = _build_argv_callable(module, exec_name)
    return AgentRuntimeConfig(
        name=agent_name,
        exec=exec_name,
        exit_sequence=exit_sequence,
        get_session_id=get_session_id,
        build_argv=build_argv,
        source=source,
    )


def _exit_sequence_from_module(module: ModuleType) -> bytes:
    if hasattr(module, "EXIT_SEQUENCE"):
        return _required_attr(module, "EXIT_SEQUENCE", bytes)
    exit_command = _required_attr(module, "EXIT_COMMAND", str)
    return encode_input(exit_command)


def _required_attr(module: ModuleType, name: str, expected_type: type) -> Any:
    if not hasattr(module, name):
        raise AgentConfigError(f"missing {name}")
    value = getattr(module, name)
    if not isinstance(value, expected_type):
        raise AgentConfigError(f"{name} must be {expected_type.__name__}")
    return value


def _required_callable(module: ModuleType, name: str) -> Callable[..., Any]:
    if not hasattr(module, name):
        raise AgentConfigError(f"missing {name}")
    value = getattr(module, name)
    if not callable(value):
        raise AgentConfigError(f"{name} must be callable")
    return value


def _build_argv_callable(module: ModuleType, exec_name: str) -> Callable[[str, str | None], list[str]]:
    if hasattr(module, "build_argv"):
        build_argv = getattr(module, "build_argv")
        if not callable(build_argv):
            raise AgentConfigError("build_argv must be callable")
        return build_argv

    def default_build_argv(prompt_text: str, session_id: str | None = None) -> list[str]:
        if session_id is None:
            return [exec_name, prompt_text]
        return [exec_name, "resume", session_id, prompt_text]

    return default_build_argv


def _log(logger: Callable[[str], None] | None, message: str) -> None:
    if logger is not None:
        logger(message)
        return
    logging.getLogger(__name__).info(message)
