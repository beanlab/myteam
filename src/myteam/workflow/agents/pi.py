from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_utils import resolve_session_path, iter_jsonl_reverse, estimate_usage_cost
from .runtime import AgentSessionContext
from .codex import PRICING_INFO
from ..definition.models import UsageInfo

EXEC = "pi"
SESSION_ID_RE = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$")
EXIT_COMMAND = "/quit"


def build_argv(
    prompt_text: str,
    interactive: bool = True,
    session_id: str | None = None,
    fork: bool = False,
    model: str | None = None,
    extra_args: list[str] | None = None,
) -> list[str]:
    extras = extra_args or []
    if model is not None:
        extras = ["--model", model, *extras]
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


def get_session_info(nonce: str, context: AgentSessionContext) -> tuple[str, Path]:
    session_path = _resolve_pi_session_path(nonce, context)
    match = SESSION_ID_RE.search(session_path.name)
    if match is None:
        raise LookupError(f"No Pi session found for nonce: {nonce}")
    return match.group(1), session_path


def get_usage_info(session_path: Path) -> UsageInfo | None:
    try:
        return _usage_info_from_session_path(session_path)
    except (LookupError, ValueError, json.JSONDecodeError):
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

    estimated_cost = _get_explicit_total_cost(latest_usage)
    if estimated_cost is None:
        estimated_cost = estimate_usage_cost(
            PRICING_INFO,
            latest_model,
            int(latest_usage.get("input", 0)),
            int(latest_usage.get("cacheRead", 0)),
            int(latest_usage.get("output", 0)),
        )

    return UsageInfo(
        model=latest_model,
        input_tokens=int(latest_usage.get("input", 0)),
        cached_input_tokens=int(latest_usage.get("cacheRead", 0)),
        output_tokens=int(latest_usage.get("output", 0)),
        reasoning_output_tokens=0,
        total_tokens=int(latest_usage.get("totalTokens", 0)),
        estimated_cost=estimated_cost,
    )


def _project_session_dir_name(path: Path) -> str:
    project_path = path.resolve().as_posix().strip("/")
    return f"--{project_path.replace('/', '-')}--"


def _get_explicit_total_cost(usage: dict[str, Any]) -> float | None:
    cost = usage.get("cost")
    if not isinstance(cost, dict) or "total" not in cost:
        return None

    try:
        return float(cost["total"])
    except (TypeError, ValueError):
        return None
