from __future__ import annotations

import json
import re
from pathlib import Path

from .pricing import estimate_usage_cost
from .session_files import resolve_session_path
from .runtime import AgentSessionContext
from ..models import UsageInfo

EXEC = "codex"
SESSION_ID_RE = re.compile(r"rollout-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-([0-9a-f-]{36})\.jsonl$")
MODEL_RE = re.compile(r'"model"\s*:\s*"([^"]+)"')
EXIT_COMMAND = "/quit"


def build_argv(
    prompt_text: str,
    interactive: bool = True,
    session_id: str | None = None,
    fork: bool = False,
    extra_args: list[str] | None = None,
) -> list[str]:
    extras = extra_args or []
    if not interactive and fork:
        raise ValueError("Codex non-interactive workflow steps do not support fork.")
    if not interactive and session_id is not None:
        return [EXEC, "exec", "resume", session_id, *extras, prompt_text]
    if session_id is not None and fork:
        return [EXEC, "fork", session_id, *extras, prompt_text]
    if session_id is not None:
        return [EXEC, "resume", session_id, *extras, prompt_text]
    if not interactive:
        return [EXEC, "exec", *extras, prompt_text]
    return [EXEC, *extras, prompt_text]


def get_session_id(nonce: str, context: AgentSessionContext) -> str:
    session_path = resolve_session_path(
        nonce,
        (context.home / ".codex" / "sessions",),
        "rollout-*.jsonl",
    )
    match = SESSION_ID_RE.search(session_path.name)
    if match is None:
        raise LookupError(f"No Codex session found for nonce: {nonce}")
    return match.group(1)


def get_usage_info(nonce: str, context: AgentSessionContext) -> UsageInfo | None:
    try:
        session_path = resolve_session_path(
            nonce,
            (context.home / ".codex" / "sessions",),
            "rollout-*.jsonl",
        )
        return _usage_info_from_session_path(session_path)
    except (LookupError, OSError, ValueError, json.JSONDecodeError):
        return None


def _usage_info_from_session_path(path: Path) -> UsageInfo | None:
    model: str | None = None
    token_usage: dict[str, object] | None = None

    with path.open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if model is None:
                match = MODEL_RE.search(line)
                if match is not None:
                    model = match.group(1)
            if token_usage is None and '"type"' in line and "token_count" in line:
                try:
                    record = json.loads(line)
                except (ValueError, TypeError, json.JSONDecodeError):
                    continue
                if not isinstance(record, dict) or record.get("type") != "token_count":
                    continue
                info = record.get("info")
                if not isinstance(info, dict):
                    continue
                usage = info.get("total_token_usage")
                if not isinstance(usage, dict):
                    continue
                token_usage = usage
            if model is not None and token_usage is not None:
                break

    if model is None or token_usage is None:
        return None

    values = _usage_tokens_from_total_usage(token_usage)
    if values is None:
        return None
    input_tokens, cached_input_tokens, output_tokens, reasoning_output_tokens, total_tokens = values
    return UsageInfo(
        model=model,
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        reasoning_output_tokens=reasoning_output_tokens,
        total_tokens=total_tokens,
        estimated_cost=estimate_usage_cost(
            model,
            input_tokens,
            cached_input_tokens,
            output_tokens,
        ),
    )


def _usage_tokens_from_total_usage(token_usage: dict[str, object]) -> tuple[int, int, int, int, int] | None:
    input_tokens = _int_field(token_usage, "input_tokens")
    cached_input_tokens = _int_field(token_usage, "cached_input_tokens")
    output_tokens = _int_field(token_usage, "output_tokens")
    reasoning_output_tokens = _int_field(token_usage, "reasoning_output_tokens")
    total_tokens = _int_field(token_usage, "total_tokens")
    if None in (
        input_tokens,
        cached_input_tokens,
        output_tokens,
        reasoning_output_tokens,
        total_tokens,
    ):
        return None
    return (
        input_tokens,
        cached_input_tokens,
        output_tokens,
        reasoning_output_tokens,
        total_tokens,
    )


def _int_field(mapping: dict[str, object], key: str) -> int | None:
    value = mapping.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None
