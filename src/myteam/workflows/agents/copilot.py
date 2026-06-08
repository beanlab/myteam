from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent_utils import estimate_usage_cost, iter_jsonl_reverse, resolve_session_path
from .codex import PRICING_INFO
from .runtime import AgentSessionContext
from ...tasks.definition import UsageInfo

EXEC = "copilot"
EXIT_COMMAND = "/quit"


def build_argv(
    prompt_text: str,
    interactive: bool = True,
    session_id: str | None = None,
    fork: bool = False, # not supported by copilot
    model: str | None = None,
    extra_args: tuple[str, ...] | None = None,
) -> list[str]:
    extras = list(extra_args or [])
    if model is not None:
        extras = [f"--model={model}", *extras]

    argv = [EXEC]
    if not interactive:
        argv.extend([f"--prompt={prompt_text}", "--no-ask-user"])

    if session_id is not None:
        argv.append(f"--resume={session_id}")

    argv.extend(extras)
    if interactive:
        argv.append(f"--interactive={prompt_text}")
    return argv


def get_session_info(nonce: str, context: AgentSessionContext) -> tuple[str, Path]:
    session_path = resolve_session_path(
        nonce,
        (context.home / ".copilot" / "session-state",),
        "events.jsonl",
    )
    session_id = session_path.parent.name
    if not session_id:
        raise LookupError(f"No Copilot session found for nonce: {nonce}")
    return session_id, session_path


def get_usage_info(session_path: Path) -> UsageInfo | None:
    latest_model: str | None = None
    latest_usage: dict[str, Any] | None = None

    for event in iter_jsonl_reverse(session_path):
        if latest_model is None:
            latest_model = _extract_string(
                event,
                "model",
                "payload.model",
                "data.model",
                "message.model",
            )

        if latest_usage is None:
            latest_usage = _extract_usage_payload(event)

        if latest_model is not None and latest_usage is not None:
            break
    else:
        return None

    if not latest_model or not latest_usage:
        return None

    estimated_cost = _get_explicit_total_cost(latest_usage)
    if estimated_cost is None:
        estimated_cost = estimate_usage_cost(
            PRICING_INFO,
            latest_model,
            _usage_int(
                latest_usage,
                "input_tokens",
                "prompt_tokens",
                "input",
                "promptTokens",
                "inputTokens",
            ),
            _usage_int(
                latest_usage,
                "cached_input_tokens",
                "cacheRead",
                "cachedPromptTokens",
                "cachedInputTokens",
            ),
            _usage_int(
                latest_usage,
                "output_tokens",
                "output",
                "completion_tokens",
                "outputTokens",
            ),
        )

    return UsageInfo(
        model=latest_model,
        input_tokens=_usage_int(
            latest_usage,
            "input_tokens",
            "prompt_tokens",
            "input",
            "promptTokens",
            "inputTokens",
        ),
        cached_input_tokens=_usage_int(
            latest_usage,
            "cached_input_tokens",
            "cacheRead",
            "cachedPromptTokens",
            "cachedInputTokens",
        ),
        output_tokens=_usage_int(
            latest_usage,
            "output_tokens",
            "output",
            "completion_tokens",
            "outputTokens",
        ),
        reasoning_output_tokens=_usage_int(
            latest_usage,
            "reasoning_output_tokens",
            "reasoningTokens",
            "reasoning",
        ),
        total_tokens=_usage_int(latest_usage, "total_tokens", "totalTokens", "tokens"),
        estimated_cost=estimated_cost,
    )


def _extract_usage_payload(event: dict[str, object]) -> dict[str, Any] | None:
    payload = event.get("payload")
    if isinstance(payload, dict):
        usage = _usage_dict_from_mapping(payload)
        if usage is not None:
            return usage

    data = event.get("data")
    if isinstance(data, dict):
        usage = _usage_dict_from_mapping(data)
        if usage is not None:
            return usage

    return _usage_dict_from_mapping(event)


def _usage_dict_from_mapping(mapping: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("usage", "copilotUsage", "token_usage", "total_token_usage"):
        value = mapping.get(key)
        if isinstance(value, dict):
            return value

    model_metrics = mapping.get("modelMetrics")
    if isinstance(model_metrics, dict):
        for value in model_metrics.values():
            if isinstance(value, dict):
                candidate = _usage_dict_from_mapping(value)
                if candidate is not None:
                    return candidate
                if any(
                    key in value
                    for key in (
                        "input_tokens",
                        "prompt_tokens",
                        "input",
                        "inputTokens",
                        "promptTokens",
                        "output_tokens",
                        "output",
                        "total_tokens",
                        "totalTokens",
                        "outputTokens",
                    )
                ):
                    return value

    nested_usage = mapping.get("total_token_usage")
    if isinstance(nested_usage, dict):
        return nested_usage

    return None


def _extract_string(mapping: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = _nested_get(mapping, key)
        if isinstance(value, str):
            return value
    return None


def _nested_get(mapping: dict[str, object], dotted_key: str) -> object | None:
    current: object = mapping
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _usage_int(mapping: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
    return 0


def _get_explicit_total_cost(usage: dict[str, Any]) -> float | None:
    cost = usage.get("cost")
    if not isinstance(cost, dict) or "total" not in cost:
        return None

    try:
        return float(cost["total"])
    except (TypeError, ValueError):
        return None
