from __future__ import annotations

import json

from .pricing import estimate_usage_cost
from .agent_utils import resolve_session_path, iter_jsonl_reverse
from .runtime import AgentSessionContext
from ..models import UsageInfo

EXEC = "codex"
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
    path = resolve_session_path(
        nonce,
        (context.home / ".codex" / "sessions",),
        "rollout-*.jsonl",
    )

    stem = path.stem
    if "-" not in stem:
        raise LookupError(f"No Codex session found for nonce: {nonce}")

    return stem.rsplit("-", 1)[-1]


def get_usage_info(nonce: str, context: AgentSessionContext) -> UsageInfo | None:
    try:
        path = resolve_session_path(
            nonce,
            (context.home / ".codex" / "sessions",),
            "rollout-*.jsonl",
        )
    except (LookupError, OSError):
        return None
    model = None
    try:
        for line in iter_jsonl_reverse(path):
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            # capture model (first valid from bottom = last in file)
            if model is None:
                payload = event.get("payload")
                if isinstance(payload, dict):
                    m = payload.get("model")
                    if isinstance(m, str):
                        model = m
            if event.get("type") != "event_msg":
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            if payload.get("type") != "token_count":
                continue
            info = payload.get("info")
            if not isinstance(info, dict):
                continue
            usage = info.get("total_token_usage")
            if not isinstance(usage, dict):
                continue
            # found final usage → stop immediately
            break

        else:
            return None

    except OSError:
        return None

    if not model:
        return None

    def get_token_count(k: str) -> int:
        v = usage.get(k)
        return v if isinstance(v, int) else 0

    input_tokens = get_token_count("input_tokens")
    cached_input_tokens = get_token_count("cached_input_tokens")
    output_tokens = get_token_count("output_tokens")
    reasoning_tokens = get_token_count("reasoning_output_tokens")
    total_tokens = get_token_count("total_tokens")

    return UsageInfo(
        model=model,
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        reasoning_output_tokens=reasoning_tokens,
        total_tokens=total_tokens,
        estimated_cost=estimate_usage_cost(
            model,
            input_tokens,
            cached_input_tokens,
            output_tokens,
        ),
    )
