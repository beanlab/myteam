from __future__ import annotations

import re
from pathlib import Path

from .agent_utils import resolve_session_path, iter_jsonl, estimate_usage_cost
from .runtime import AgentSessionContext
from ..results import UsageInfo

EXEC = "codex"
EXIT_COMMAND = "/quit"
SESSION_ID_RE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$"
)
# model: (input, cached input, output) rate per 1M tokens
PRICING_INFO: dict[str, tuple[float, float | None, float]] = {
    "gpt-5.5": (5.0, 0.5, 30.0),
    "gpt-5.5-pro": (30.0, None, 180.0),
    "gpt-5.4": (2.5, 0.25, 15.0),
    "gpt-5.4-mini": (0.75, 0.075, 4.5),
    "gpt-5.4-nano": (0.2, 0.02, 1.25),
    "gpt-5.4-pro": (30.0, None, 180.0),
    "gpt-5.3-codex": (1.75, 0.175, 14.0),
    "gpt-5.2": (1.75, 0.175, 14.0),
    "gpt-5.2-codex": (1.75, 0.175, 14.0),
    "gpt-5.2-pro": (21.0, None, 168.0),
    "gpt-5": (1.25, 0.125, 10.0),
    "gpt-5-codex": (1.25, 0.125, 10.0),
    "gpt-5-pro": (15.0, None, 120.0),
    "gpt-5-mini": (0.25, 0.025, 2.0),
    "gpt-5-nano": (0.05, 0.005, 0.4),
}


def build_argv(
    prompt_text: str,
    interactive: bool = True,
    session_id: str | None = None,
    fork: bool = False,
    model: str | None = None,
    extra_args: tuple[str, ...] | None = None,
) -> list[str]:
    extras = extra_args or []
    if model is not None:
        extras = ["--model", model, *extras]
    if not interactive and fork:
        raise ValueError("Codex non-interactive task steps do not support fork.")
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


def get_usage_info(session_path: Path) -> list[UsageInfo] | None:
    current_model: str | None = None
    previous_usage: dict[str, object] = {}
    usage_by_model: dict[str, UsageInfo] = {}

    for event in iter_jsonl(session_path):
        model = _extract_model(event)
        if model is not None:
            current_model = model

        cumulative_usage = _extract_usage_payload(event)
        if cumulative_usage is None:
            continue

        usage_delta = _usage_delta(cumulative_usage, previous_usage)
        previous_usage = cumulative_usage
        if current_model is None:
            continue

        input_tokens = usage_delta["input_tokens"]
        cached_input_tokens = usage_delta["cached_input_tokens"]
        output_tokens = usage_delta["output_tokens"]
        model_usage = usage_by_model.setdefault(
            current_model,
            UsageInfo(model=current_model),
        )
        model_usage.add(
            UsageInfo(
                model=current_model,
                input_tokens=input_tokens,
                cached_input_tokens=cached_input_tokens,
                output_tokens=output_tokens,
                reasoning_output_tokens=usage_delta["reasoning_output_tokens"],
                total_tokens=usage_delta["total_tokens"],
                estimated_cost=estimate_usage_cost(
                    PRICING_INFO,
                    current_model,
                    input_tokens,
                    cached_input_tokens,
                    output_tokens,
                ),
            )
        )

    return list(usage_by_model.values()) or None


def _extract_model(event: dict[str, object]) -> str | None:
    payload = event.get("payload")
    if isinstance(payload, dict) and isinstance(payload.get("model"), str):
        return payload["model"]
    model = event.get("model")
    return model if isinstance(model, str) else None


def _usage_delta(
    current: dict[str, object],
    previous: dict[str, object],
) -> dict[str, int]:
    fields = (
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
        "total_tokens",
    )
    delta: dict[str, int] = {}
    for field in fields:
        current_value = current.get(field)
        previous_value = previous.get(field)
        current_count = current_value if isinstance(current_value, int) else 0
        previous_count = previous_value if isinstance(previous_value, int) else 0
        delta[field] = (
            current_count - previous_count
            if current_count >= previous_count
            else current_count
        )
    return delta


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
