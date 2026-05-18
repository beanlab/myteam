from __future__ import annotations

import re
from pathlib import Path

from .pricing import estimate_usage_cost
from .session_files import resolve_session_path
from .runtime import AgentSessionContext
from ..models import UsageInfo

EXEC = "pi"
SESSION_ID_RE = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$")
MODEL_RE = re.compile(r'"model"\s*:\s*"([^"]+)"')
INPUT_RE = re.compile(r'"input"\s*:\s*(\d+)')
OUTPUT_RE = re.compile(r'"output"\s*:\s*(\d+)')
CACHE_READ_RE = re.compile(r'"cacheRead"\s*:\s*(\d+)')
TOTAL_TOKENS_RE = re.compile(r'"totalTokens"\s*:\s*(\d+)')
REASONING_OUTPUT_RE = re.compile(r'"reasoningOutputTokens"\s*:\s*(\d+)')
COST_TOTAL_RE = re.compile(r'"cost"\s*:\s*\{[^}]*"total"\s*:\s*([0-9]+(?:\.[0-9]+)?)')
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
    sessions_dir = context.home / ".pi" / "agent" / "sessions"
    project_sessions_dir = sessions_dir / _project_session_dir_name(context.launch_cwd)
    session_path = resolve_session_path(
        nonce,
        (project_sessions_dir, sessions_dir),
        "*.jsonl",
    )
    match = SESSION_ID_RE.search(session_path.name)
    if match is None:
        raise LookupError(f"No Pi session found for nonce: {nonce}")
    return match.group(1)


def get_usage_info(nonce: str, context: AgentSessionContext) -> UsageInfo | None:
    sessions_dir = context.home / ".pi" / "agent" / "sessions"
    project_sessions_dir = sessions_dir / _project_session_dir_name(context.launch_cwd)
    try:
        session_path = resolve_session_path(
            nonce,
            (project_sessions_dir, sessions_dir),
            "*.jsonl",
        )
        return _usage_info_from_session_path(session_path)
    except (LookupError, OSError, ValueError):
        return None


def _usage_info_from_session_path(path: Path) -> UsageInfo | None:
    model: str | None = None
    usage: dict[str, object] | None = None

    with path.open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if model is None:
                match = MODEL_RE.search(line)
                if match is not None:
                    model = match.group(1)
            if usage is None and '"usage"' in line and '"api"' in line:
                usage_candidate = _usage_dict_from_line(line)
                if usage_candidate is None:
                    continue
                usage = usage_candidate
            if model is not None and usage is not None:
                break

    if model is None or usage is None:
        return None

    values = _usage_values_from_usage(model, usage)
    if values is None:
        return None
    input_tokens, cached_input_tokens, output_tokens, reasoning_output_tokens, total_tokens, estimated_cost = values
    return UsageInfo(
        model=model,
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        reasoning_output_tokens=reasoning_output_tokens,
        total_tokens=total_tokens,
        estimated_cost=estimated_cost,
    )


def _usage_dict_from_line(line: str) -> dict[str, object] | None:
    input_tokens = _int_match(INPUT_RE, line)
    cached_input_tokens = _int_match(CACHE_READ_RE, line)
    output_tokens = _int_match(OUTPUT_RE, line)
    total_tokens = _int_match(TOTAL_TOKENS_RE, line)
    if None in (input_tokens, cached_input_tokens, output_tokens, total_tokens):
        return None

    reasoning_output_tokens = _int_match(REASONING_OUTPUT_RE, line) or 0
    usage: dict[str, object] = {
        "input": input_tokens,
        "output": output_tokens,
        "cacheRead": cached_input_tokens,
        "totalTokens": total_tokens,
        "reasoningOutputTokens": reasoning_output_tokens,
    }
    match = COST_TOTAL_RE.search(line)
    if match is not None:
        usage["cost"] = {"total": float(match.group(1))}
    return usage


def _usage_values_from_usage(
    model: str,
    usage: dict[str, object],
) -> tuple[int, int, int, int, int, float] | None:
    input_tokens = _int_field(usage, "input")
    cached_input_tokens = _int_field(usage, "cacheRead")
    output_tokens = _int_field(usage, "output")
    total_tokens = _int_field(usage, "totalTokens")
    reasoning_output_tokens = _int_field(usage, "reasoningOutputTokens") or 0
    if None in (input_tokens, cached_input_tokens, output_tokens, total_tokens):
        return None

    cost = usage.get("cost")
    estimated_cost = _usage_cost_from_cost_object(cost)
    if estimated_cost is None:
        estimated_cost = estimate_usage_cost(
            model or "",
            input_tokens,
            cached_input_tokens,
            output_tokens,
        )
    return (
        input_tokens,
        cached_input_tokens,
        output_tokens,
        reasoning_output_tokens,
        total_tokens,
        estimated_cost,
    )


def _usage_cost_from_cost_object(cost: object) -> float | None:
    if not isinstance(cost, dict):
        return None
    total = cost.get("total")
    if isinstance(total, (int, float)) and not isinstance(total, bool):
        return float(total)
    return None


def _int_field(mapping: dict[str, object], key: str) -> int | None:
    value = mapping.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _int_match(pattern: re.Pattern[str], line: str) -> int | None:
    match = pattern.search(line)
    if match is None:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _project_session_dir_name(path: Path) -> str:
    project_path = path.resolve().as_posix().strip("/")
    return f"--{project_path.replace('/', '-')}--"
