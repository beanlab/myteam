from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterator

from .agent_utils import resolve_session_path, iter_jsonl_reverse
from .runtime import AgentSessionContext
from ..models import UsageInfo

EXEC = "pi"
SESSION_ID_RE = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$")
EXIT_COMMAND = "/quit"


def build_argv(
    prompt_text: str,
    interactive: bool = True,
    session_id: str | None = None,
    fork: bool = False,
    extra_args: list[str] | None = None,
) -> list[str]:
    extras = extra_args or []
    argv = [EXEC]
    if not interactive:
        argv.append("--print")
    if session_id is not None:
        if fork:
            argv.extend(["--fork", session_id])
        else:
            argv.extend(["--session", session_id])
    argv.extend(extras)
    argv.append(prompt_text)
    return argv


def get_session_id(nonce: str, context: AgentSessionContext) -> str:
    session_path = _resolve_pi_session_path(nonce, context)
    match = SESSION_ID_RE.search(session_path.name)
    if match is None:
        raise LookupError(f"No Pi session found for nonce: {nonce}")
    return match.group(1)


def get_usage_info(
    nonce: str,
    context: AgentSessionContext,
) -> UsageInfo | None:
    try:
        session_path = _resolve_pi_session_path(nonce, context)
        return _usage_info_from_session_path(session_path)
    except (LookupError, OSError, ValueError, json.JSONDecodeError):
        return None


def _resolve_pi_session_path(
    nonce: str,
    context: AgentSessionContext,
) -> Path:
    sessions_dir = context.home / ".pi" / "agent" / "sessions"
    project_sessions_dir = sessions_dir / _project_session_dir_name(context.launch_cwd)

    return resolve_session_path(
        nonce,
        (project_sessions_dir, sessions_dir),
        "*.jsonl",
    )


def _usage_info_from_session_path(path: Path) -> UsageInfo | None:
    latest_model: str | None = None
    latest_usage: dict[str, Any] | None = None

    for payload in iter_jsonl_reverse(path):
        message = payload.get("message")
        if not isinstance(message, dict):
            message = payload

        model = message.get("model")
        usage = message.get("usage")

        if latest_model is None and isinstance(model, str):
            latest_model = model

        if isinstance(usage, dict):
            latest_usage = usage

        if latest_model and latest_usage:
            break

    if not latest_model or not latest_usage:
        return None

    cost = latest_usage.get("cost") or {}

    return UsageInfo(
        model=latest_model,
        input_tokens=int(latest_usage.get("input", 0)),
        cached_input_tokens=int(latest_usage.get("cacheRead", 0)),
        output_tokens=int(latest_usage.get("output", 0)),
        reasoning_output_tokens=0,
        total_tokens=int(latest_usage.get("totalTokens", 0)),
        estimated_cost=float(cost.get("total", 0.0)),
    )


def _project_session_dir_name(path: Path) -> str:
    project_path = path.resolve().as_posix().strip("/")
    return f"--{project_path.replace('/', '-')}--"
