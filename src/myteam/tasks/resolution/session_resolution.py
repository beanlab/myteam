from __future__ import annotations

import os
from pathlib import Path

from ...disclosure import MYTEAM_ROOT_DIR_ENV_VAR_NAME
from ..execution.errors import StepExecutionError
from ..agents.runtime import AgentRuntimeConfig


def resolve_project_root(cwd: Path | None = None) -> Path:
    configured_agent_root = os.environ.get(MYTEAM_ROOT_DIR_ENV_VAR_NAME)
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
    payload: dict | None,
    session_id: str | None,
    fork: bool,
    nonce: str | None,
    agent_config: AgentRuntimeConfig,
) -> tuple[str, Path | None] | None:
    if nonce is None:
        return None
    try:
        session_info = agent_config.get_session_info(nonce)
    except LookupError as exc:
        session_info = None
        session_lookup_error = exc
    discovered_session_id = None if payload is None else payload.get("session_id")
    if discovered_session_id is None and session_id is not None and not fork:
        discovered_session_id = session_id
    if discovered_session_id is not None:
        return discovered_session_id, None if session_info is None else session_info[1]
    if session_info is None:
        raise StepExecutionError("session_discovery", str(session_lookup_error)) from session_lookup_error
    return session_info
