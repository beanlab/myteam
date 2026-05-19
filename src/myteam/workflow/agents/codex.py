from __future__ import annotations

import re
from pathlib import Path

from .agent_utils import resolve_session_path, iter_jsonl_reverse, estimate_usage_cost
from .runtime import AgentSessionContext
from ..models import UsageInfo

EXEC = "codex"
EXIT_COMMAND = "/quit"
SESSION_ID_RE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$"
)
# model: [input, cached, output]
PRICING_INFO = {
    "gpt-5.5": [5.0, 0.5, 30.0],
    "gpt-5.4": [2.5, 0.25, 15.0],
    "gpt-5.4-mini": [0.75, 0.075, 4.5],
    "gpt-5.4-nano": [0.2, 0.02, 1.25],
    "gpt-5.2": [1.75, 0.175, 14.00],
    "gpt-5": [1.25, 0.125, 10.00],
    "gpt-5-mini": [0.25, 0.025, 2.00],
    "gpt-5-nano": [0.05, 0.005, 0.40],
}


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


def get_session_info(nonce: str, context: AgentSessionContext) -> tuple[str, Path]:
    path = resolve_session_path(
        nonce,
        (context.home / ".codex" / "sessions",),
        "rollout-*.jsonl",
    )

    match = SESSION_ID_RE.search(path.stem)
    if match is None:
        raise LookupError(f"No Codex session found for nonce: {nonce}")

    return match.group(1), path


def get_usage_info(session_path: Path) -> UsageInfo | None:
    model = None
    usage: dict[str, object] | None = None
    for event in iter_jsonl_reverse(session_path):
        # capture model (first valid from bottom = last in file)
        if model is None:
            payload = event.get("payload")
            if isinstance(payload, dict):
                m = payload.get("model")
                if isinstance(m, str):
                    model = m
            elif isinstance(event.get("model"), str):
                model = event["model"]

        if usage is None:
            usage = _extract_usage_payload(event)

        if model is not None and usage is not None:
            # found final usage → stop immediately
            break

    else:
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
            PRICING_INFO,
            model,
            input_tokens,
            cached_input_tokens,
            output_tokens,
        ),
    )


def _extract_usage_payload(event: dict[str, object]) -> dict[str, object] | None:
    payload = event.get("payload")
    if isinstance(payload, dict):
        if payload.get("type") == "token_count":
            info = payload.get("info")
            if isinstance(info, dict):
                usage = info.get("total_token_usage")
                if isinstance(usage, dict):
                    return usage
        nested_usage = payload.get("total_token_usage")
        if isinstance(nested_usage, dict):
            return nested_usage

    if event.get("type") == "token_count":
        info = event.get("info")
        if isinstance(info, dict):
            usage = info.get("total_token_usage")
            if isinstance(usage, dict):
                return usage

    usage = event.get("usage")
    if isinstance(usage, dict):
        return usage

    return None
