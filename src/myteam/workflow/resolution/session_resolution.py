from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ...disclosure import PROJECT_ROOT_ENV_VAR
from ..execution.errors import StepExecutionError
from ..agents.runtime import AgentRuntimeConfig


def resolve_project_root(cwd: Path | None = None) -> Path:
    configured_agent_root = os.environ.get(PROJECT_ROOT_ENV_VAR)
    if configured_agent_root:
        return Path(configured_agent_root).resolve().parent

    if cwd is None:
        cwd = Path.cwd()

    cwd = cwd.resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / ".myteam").is_dir():
            return candidate
    return cwd


def resolve_session_id(
    *,
    payload: Any,
    session_id: str | None,
    fork: bool,
    nonce: str | None,
    agent_config: AgentRuntimeConfig,
) -> tuple[str, Path | None] | None:
    if nonce is None:
        return None

    session_lookup_error: LookupError | None = None
    try:
        session_info = agent_config.get_session_info(nonce)
    except LookupError as exc:
        session_lookup_error = exc
        session_info = None

    payload_session_id = extract_session_id(payload)
    if payload_session_id is not None:
        return payload_session_id, None if session_info is None else session_info[1]
    if session_id is not None and not fork:
        return session_id, None if session_info is None else session_info[1]
    if session_info is None:
        assert session_lookup_error is not None
        raise StepExecutionError("session_discovery", str(session_lookup_error)) from session_lookup_error
    return session_info


def extract_session_id(output_value: Any) -> str | None:
    if not isinstance(output_value, dict):
        return None
    value = output_value.get("session_id")
    if isinstance(value, str) and value:
        return value
    return None
