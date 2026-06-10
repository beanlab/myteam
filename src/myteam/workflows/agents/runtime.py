from __future__ import annotations

import importlib
import importlib.util
import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from .agent_utils import encode_input
from ..results import UsageInfo


@dataclass(frozen=True)
class AgentSessionContext:
    home: Path
    project_root: Path
    launch_cwd: Path

    @property
    def user_home(self) -> Path:
        return self.home


@dataclass(frozen=True)
class AgentRuntimeConfig:
    name: str
    exec: str
    exit_sequence: bytes
    get_session_info: Callable[[str], tuple[str, Path]]
    build_argv: Callable[
        [str, bool, str | None, bool, str | None, list[str] | None],
        list[str],
    ]
    source: Path | str
    get_usage_info: Callable[[Path], UsageInfo | None] | None = None


class AgentConfigError(Exception):
    pass


def resolve_agent_runtime_config(
    name: str | None,
    *,
    project_root: Path,
    session_context: AgentSessionContext,
    logger: Callable[[str], None] | None = None,
) -> AgentRuntimeConfig:
    agent_name = _require_agent_name(name)
    local_error: Exception | None = None
    local_path = _local_agent_config_path(project_root, agent_name)

    if local_path is not None:
        try:
            module, class_name = _load_config_target(agent_name, local_path)
            config = _config_from_module(
                agent_name,
                module,
                class_name=class_name,
                source=local_path,
                session_context=session_context,
            )
        except Exception as exc:
            local_error = exc
            _log(
                logger,
                f"Local workflow agent config '{local_path}' is unusable: {exc}. "
                "Falling back to packaged default.",
            )
        else:
            _log(logger, f"Using local workflow agent config '{local_path}'.")
            return config

    try:
        module = importlib.import_module(f"myteam.workflows.agents.{agent_name}")
        config = _config_from_module(
            agent_name,
            module,
            source=f"myteam.workflows.agents.{agent_name}",
            session_context=session_context,
        )
    except ModuleNotFoundError as exc:
        if exc.name == f"myteam.workflows.agents.{agent_name}":
            if local_error is not None:
                raise KeyError(
                    f"Invalid local workflow agent config for {agent_name}: {local_error}"
                ) from local_error
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


def _config_from_module(
    agent_name: str,
    module: ModuleType,
    *,
    class_name: str | None = None,
    source: Path | str,
    session_context: AgentSessionContext,
) -> AgentRuntimeConfig:
    config_object = _instantiate_config_class(module, class_name) if class_name else module
    exec_name = getattr(config_object, "EXEC", None) or getattr(config_object, "exec", None) or agent_name
    if not isinstance(exec_name, str):
        raise AgentConfigError("agent executable name must be a string")
    exit_sequence = _exit_sequence_from_object(config_object)
    get_session_info = _get_session_info_callable(config_object, session_context)
    build_argv = _build_argv_callable(config_object)
    get_usage_info = _get_usage_info_callable(config_object, session_context)
    return AgentRuntimeConfig(
        name=agent_name,
        exec=exec_name,
        exit_sequence=exit_sequence,
        get_session_info=get_session_info,
        build_argv=build_argv,
        source=source,
        get_usage_info=get_usage_info,
    )


def _local_agent_config_path(project_root: Path, agent_name: str) -> str | Path | None:
    yaml_path = project_root / ".myteam.yaml"
    if yaml_path.exists():
        import yaml

        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            agents = data.get("agents")
            if isinstance(agents, dict):
                target = agents.get(agent_name)
                if isinstance(target, str) and target:
                    return target if Path(target).is_absolute() else yaml_path.parent / target

    legacy_path = project_root / ".myteam" / ".config" / f"{agent_name}.py"
    return legacy_path if legacy_path.exists() else None


def _load_config_target(agent_name: str, target: str | Path) -> tuple[ModuleType, str | None]:
    target_text = str(target)
    path_text, _, class_name = target_text.partition("::")
    module = _load_module_from_path(agent_name, Path(path_text))
    return module, class_name or None


def _instantiate_config_class(module: ModuleType, class_name: str | None) -> Any:
    if not class_name:
        return module
    config_type = getattr(module, class_name, None)
    if config_type is None:
        raise AgentConfigError(f"missing config class {class_name}")
    return config_type()


def _exit_sequence_from_object(config_object: Any) -> bytes:
    if hasattr(config_object, "get_exit_sequence"):
        value = config_object.get_exit_sequence()
        if not isinstance(value, bytes):
            raise AgentConfigError("get_exit_sequence must return bytes")
        return value
    if hasattr(config_object, "EXIT_SEQUENCE"):
        value = getattr(config_object, "EXIT_SEQUENCE")
        if not isinstance(value, bytes):
            raise AgentConfigError("EXIT_SEQUENCE must be bytes")
        return value
    exit_command = getattr(config_object, "EXIT_COMMAND", None)
    if not isinstance(exit_command, str):
        raise AgentConfigError("missing EXIT_COMMAND or get_exit_sequence")
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


def _get_session_info_callable(
    config_object: Any,
    session_context: AgentSessionContext,
) -> Callable[[str], tuple[str, Path]]:
    if hasattr(config_object, "get_session_info"):
        module_get_session_info = _required_callable(config_object, "get_session_info")
        _require_positional_parameter_count(module_get_session_info, "get_session_info", 2)

        def get_session_info(nonce: str) -> tuple[str, Path]:
            return module_get_session_info(nonce, session_context)

        return get_session_info

    if hasattr(config_object, "locate_session_data") and hasattr(config_object, "get_session_id"):
        locate_session_data = _required_callable(config_object, "locate_session_data")
        get_session_id = _required_callable(config_object, "get_session_id")

        def get_session_info(nonce: str) -> tuple[str, Path]:
            session_data = locate_session_data(nonce, session_context)
            session_id = get_session_id(session_data)
            return session_id, Path(session_data)

        return get_session_info

    raise AgentConfigError("missing get_session_info or locate_session_data/get_session_id")


def _get_usage_info_callable(
    config_object: Any,
    session_context: AgentSessionContext,
) -> Callable[[Path], UsageInfo | None] | None:
    if not hasattr(config_object, "get_usage_info"):
        return None

    module_get_usage_info = _required_callable(config_object, "get_usage_info")
    _require_positional_parameter_count(
        module_get_usage_info,
        "get_usage_info",
        1,
        error_message="get_usage_info must accept session_path",
    )

    def get_usage_info(session_path: Path) -> UsageInfo | None:
        return module_get_usage_info(session_path)

    return get_usage_info


def _require_positional_parameter_count(
    callable_value: Callable[..., Any],
    name: str,
    count: int,
    *,
    error_message: str | None = None,
) -> None:
    try:
        signature = inspect.signature(callable_value)
    except (TypeError, ValueError) as exc:
        raise AgentConfigError(f"{name} signature could not be inspected") from exc

    positional_parameters = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]
    has_varargs = any(
        parameter.kind is inspect.Parameter.VAR_POSITIONAL
        for parameter in signature.parameters.values()
    )
    if not has_varargs and len(positional_parameters) != count:
        if error_message is not None:
            raise AgentConfigError(error_message)
        raise AgentConfigError(f"{name} must accept nonce and context")


def _build_argv_callable(config_object: Any) -> Callable[
    [str, bool, str | None, bool, str | None, tuple[str, ...] | None],
    list[str],
]:
    if not hasattr(config_object, "build_argv"):
        raise AgentConfigError(
            "missing build_argv; workflow agent configs must return a list of argv strings."
        )
    build_argv = getattr(config_object, "build_argv")
    if not callable(build_argv):
        raise AgentConfigError("build_argv must be callable")

    def wrapper(
        prompt_text: str,
        interactive: bool = True,
        session_id: str | None = None,
        fork: bool = False,
        model: str | None = None,
        extra_args: tuple[str, ...] | None = None,
        reasoning: str | None = None,
    ) -> list[str]:
        kwargs = {
            "prompt_text": prompt_text,
            "model": model,
            "interactive": interactive,
            "session_id": session_id,
            "fork": fork,
            "extra_args": extra_args,
            "reasoning": reasoning,
        }
        try:
            signature = inspect.signature(build_argv)
        except (TypeError, ValueError):
            return build_argv(prompt_text, interactive, session_id, fork, model, extra_args)
        accepted = {
            key: value
            for key, value in kwargs.items()
            if key in signature.parameters
        }
        try:
            return build_argv(**accepted)
        except TypeError:
            return build_argv(prompt_text, interactive, session_id, fork, model, extra_args)

    return wrapper


def _log(logger: Callable[[str], None] | None, message: str) -> None:
    if logger is not None:
        logger(message)
        return
    logging.getLogger(__name__).info(message)
