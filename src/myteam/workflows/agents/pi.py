from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_utils import resolve_session_path, iter_jsonl_reverse, estimate_usage_cost
from .runtime import AgentSessionContext
from .codex import PRICING_INFO
from ..results import UsageInfo

EXEC = "pi"
SESSION_ID_RE = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$")
EXIT_COMMAND = "/quit"


def build_argv(
    prompt_text: str,
    interactive: bool = True,
    session_id: str | None = None,
    fork: bool = False,
    model: str | None = None,
    extra_args: tuple[str, ...] | None = None,
    session_name: str | None = None,
) -> list[str]:
    argv = [EXEC]
    if not interactive:
        argv.append("--print")
    if session_id is not None:
        if fork:
            argv.extend(["--fork", session_id])
        else:
            argv.extend(["--session", session_id])
    if model is not None:
        argv.extend(["--model", model])
    if session_name is not None:
        argv.extend(["--name", session_name])
    argv.extend(extra_args or [])
    argv.append(prompt_text)
    return argv


def get_session_info(nonce: str, context: AgentSessionContext) -> tuple[str, Path]:
    session_path = _resolve_pi_session_path(nonce, context)
    match = SESSION_ID_RE.search(session_path.name)
    if match is None:
        raise LookupError(f"No Pi session found for nonce: {nonce}")
    return match.group(1), session_path


def get_usage_info(session_path: Path) -> list[UsageInfo] | None:
    try:
        return _usage_by_model_from_session_path(session_path)
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


def _usage_by_model_from_session_path(path: Path) -> list[UsageInfo] | None:
    usage_by_model: dict[str, UsageInfo] = {}

    for payload in iter_jsonl_reverse(path):
        message = payload.get("message")
        if not isinstance(message, dict):
            message = payload

        model = message.get("model")
        usage = message.get("usage")
        if not isinstance(model, str) or not isinstance(usage, dict):
            continue

        cache_read_tokens = int(usage.get("cacheRead", 0))
        input_tokens = (
            int(usage.get("input", 0))
            + cache_read_tokens
            + int(usage.get("cacheWrite", 0))
        )
        estimated_cost = _get_explicit_total_cost(usage)
        if estimated_cost is None:
            estimated_cost = estimate_usage_cost(
                PRICING_INFO,
                model,
                input_tokens,
                cache_read_tokens,
                int(usage.get("output", 0)),
            )

        model_usage = usage_by_model.setdefault(model, UsageInfo(model=model))
        model_usage.add(
            UsageInfo(
                model=model,
                input_tokens=input_tokens,
                cached_input_tokens=cache_read_tokens,
                output_tokens=int(usage.get("output", 0)),
                reasoning_output_tokens=int(usage.get("reasoning", 0)),
                total_tokens=int(usage.get("totalTokens", 0)),
                estimated_cost=estimated_cost,
            )
        )

    return list(usage_by_model.values()) or None


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
