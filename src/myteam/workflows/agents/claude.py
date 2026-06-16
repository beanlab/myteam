from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from .agent_utils import iter_jsonl_reverse, resolve_session_path
from .runtime import AgentSessionContext
from ..results import UsageInfo

EXEC = "claude"
EXIT_COMMAND = "/exit"
SESSION_ID_RE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$",
    re.IGNORECASE,
)

# model: (input, cached input, output) rate per 1M tokens.
# Claude Code computes exact billing internally for `/usage`; these rates are a
# best-effort estimate from Anthropic API pricing for the common model IDs and
# aliases that may appear in local Claude Code transcripts.
PRICING_INFO: dict[str, tuple[float, float | None, float]] = {
    "fable": (10.0, 1.0, 50.0),
    "claude-fable-5": (10.0, 1.0, 50.0),
    "claude-mythos-5": (10.0, 1.0, 50.0),
    "claude-mythos-preview": (10.0, 1.0, 50.0),
    "opus": (5.0, 0.5, 25.0),
    "claude-opus-4-8": (5.0, 0.5, 25.0),
    "claude-opus-4-7": (5.0, 0.5, 25.0),
    "claude-opus-4-6": (5.0, 0.5, 25.0),
    "claude-opus-4-5": (5.0, 0.5, 25.0),
    "claude-opus-4-5-20251101": (5.0, 0.5, 25.0),
    "claude-opus-4-1-20250805": (15.0, 1.5, 75.0),
    "claude-3-opus-20240229": (15.0, 1.5, 75.0),
    "sonnet": (3.0, 0.3, 15.0),
    "claude-sonnet-4-6": (3.0, 0.3, 15.0),
    "claude-sonnet-4-5": (3.0, 0.3, 15.0),
    "claude-sonnet-4-5-20250929": (3.0, 0.3, 15.0),
    "claude-sonnet-4-20250514": (3.0, 0.3, 15.0),
    "claude-3-7-sonnet-20250219": (3.0, 0.3, 15.0),
    "claude-3-5-sonnet-20241022": (3.0, 0.3, 15.0),
    "claude-3-5-sonnet-20240620": (3.0, 0.3, 15.0),
    "haiku": (1.0, 0.1, 5.0),
    "claude-haiku-4-5": (1.0, 0.1, 5.0),
    "claude-haiku-4-5-20251001": (1.0, 0.1, 5.0),
    "claude-3-5-haiku-20241022": (0.8, 0.08, 4.0),
}


def build_argv(
    prompt_text: str,
    interactive: bool = True,
    session_id: str | None = None,
    fork: bool = False,
    model: str | None = None,
    extra_args: tuple[str, ...] | list[str] | None = None,
    reasoning: str | None = None,
) -> list[str]:
    argv = [EXEC]
    if not interactive:
        argv.append("--print")
    if session_id is not None:
        argv.extend(["--resume", session_id])
        if fork:
            argv.append("--fork-session")
    if model is not None:
        argv.extend(["--model", model])
    if reasoning is not None:
        argv.extend(["--effort", reasoning])
    argv.extend(extra_args or [])
    argv.append(prompt_text)
    return argv


def get_session_info(nonce: str, context: AgentSessionContext) -> tuple[str, Path]:
    session_path = _resolve_claude_session_path(nonce, context)
    session_id = _session_id_from_path_or_contents(session_path)
    if session_id is None:
        raise LookupError(f"No Claude session found for nonce: {nonce}")
    return session_id, session_path


def get_usage_info(session_path: Path) -> UsageInfo | None:
    latest_model: str | None = None
    latest_usage: dict[str, Any] | None = None

    for event in iter_jsonl_reverse(session_path):
        message = event.get("message")
        if not isinstance(message, dict):
            message = event

        model = message.get("model")
        if latest_model is None and isinstance(model, str):
            latest_model = model

        usage = message.get("usage")
        if isinstance(usage, dict) and latest_usage is None:
            latest_usage = usage

        if latest_model and latest_usage:
            break

    if not latest_model or not latest_usage:
        return None

    input_tokens = _int_usage(latest_usage, "input_tokens", "input")
    cache_creation_input_tokens = _int_usage(latest_usage, "cache_creation_input_tokens", "cacheCreation")
    cached_input_tokens = _int_usage(latest_usage, "cache_read_input_tokens", "cacheRead")
    output_tokens = _int_usage(latest_usage, "output_tokens", "output")
    reasoning_output_tokens = _int_usage(
        latest_usage,
        "thinking_tokens",
        "reasoning_output_tokens",
        "reasoningOutput",
    )
    total_input_tokens = input_tokens + cache_creation_input_tokens + cached_input_tokens
    total_tokens = _int_usage(latest_usage, "total_tokens", "totalTokens")
    if total_tokens == 0:
        total_tokens = total_input_tokens + output_tokens

    return UsageInfo(
        model=latest_model,
        input_tokens=total_input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        reasoning_output_tokens=reasoning_output_tokens,
        total_tokens=total_tokens,
        estimated_cost=_estimate_usage_cost(
            latest_model,
            input_tokens,
            cache_creation_input_tokens,
            cached_input_tokens,
            output_tokens,
        ),
    )


def _resolve_claude_session_path(nonce: str, context: AgentSessionContext) -> Path:
    config_dir = _claude_config_dir(context)
    sessions_root = config_dir / "projects"
    project_sessions_dir = sessions_root / _project_session_dir_name(context.launch_cwd)
    return resolve_session_path(nonce, (project_sessions_dir, sessions_root), "*.jsonl")


def _claude_config_dir(context: AgentSessionContext) -> Path:
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return context.home / ".claude"


def _project_session_dir_name(path: Path) -> str:
    project_path = path.resolve().as_posix().strip("/")
    if not project_path:
        return "-"
    return f"-{project_path.replace('/', '-')}"


def _session_id_from_path_or_contents(path: Path) -> str | None:
    match = SESSION_ID_RE.search(path.name)
    if match is not None:
        return match.group(1)

    for event in iter_jsonl_reverse(path):
        for key in ("sessionId", "session_id"):
            value = event.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _int_usage(usage: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = usage.get(key)
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _estimate_usage_cost(
    model: str,
    input_tokens: int,
    cache_creation_input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
) -> float:
    pricing = _pricing_for_model(model)
    if pricing is None:
        return 0.0

    input_rate, cached_input_rate, output_rate = pricing
    cached_rate = cached_input_rate if cached_input_rate is not None else input_rate
    return (
        input_tokens * input_rate
        + cache_creation_input_tokens * input_rate
        + cached_input_tokens * cached_rate
        + output_tokens * output_rate
    ) / 1_000_000


def _pricing_for_model(model: str) -> tuple[float, float | None, float] | None:
    candidates = _model_pricing_candidates(model)
    for candidate in candidates:
        pricing = PRICING_INFO.get(candidate)
        if pricing is not None:
            return pricing
    return None


def _model_pricing_candidates(model: str) -> tuple[str, ...]:
    normalized = model.lower().removesuffix("[1m]")
    candidates = [normalized]
    if normalized.startswith("anthropic."):
        candidates.append(normalized.removeprefix("anthropic."))
    for candidate in tuple(candidates):
        if candidate.endswith("-v1:0"):
            candidates.append(candidate.removesuffix("-v1:0"))
        if "@" in candidate:
            prefix, _, suffix = candidate.partition("@")
            candidates.append(f"{prefix}-{suffix}")
    return tuple(dict.fromkeys(candidates))
