from __future__ import annotations

from pathlib import Path
from typing import Literal

from ..agents.runtime import AgentRuntimeConfig
from ..definition.models import UsageInfo


def resolve_usage_tracking(
    *,
    agent_config: AgentRuntimeConfig,
    session_path: Path,
) -> tuple[UsageInfo | None, str, str | None]:
    if agent_config.get_usage_info is None:
        return (
            None,
            "no_get_usage_info_implemented",
            "task agent config does not implement get_usage_info",
        )

    try:
        usage = agent_config.get_usage_info(session_path)
    except Exception as exc:
        return None, "unavailable", str(exc)

    if usage is None:
        return None, "unavailable", None

    return usage, "collected", None


def resolve_usage_session_path(
    *,
    agent_config: AgentRuntimeConfig,
    nonce: str | None,
) -> Path | None:
    if nonce is None:
        return None

    try:
        _, session_path = agent_config.get_session_info(nonce)
    except LookupError:
        return None

    return session_path


def print_usage_summary(title: str, usage: UsageInfo) -> None:
    print(title)
    if usage.model:
        print(f"  Model: {usage.model}")
    print(f"  Input: {usage.input_tokens}")
    print(f"  Cached Input: {usage.cached_input_tokens}")
    print(f"  Output: {usage.output_tokens}")
    print(f"  Reasoning: {usage.reasoning_output_tokens}")
    print(f"  Total: {usage.total_tokens}")
    print(f"  Cost: ${usage.estimated_cost:.4f}")


def print_aggregated_usage_summary(
        usage_totals_by_model: dict[str, UsageInfo],
        usage_logging: Literal["none", "summary", "per_model", "verbose"] = "summary",
) -> None:
    if usage_logging == "none":
        return
    print("  Usage Summary  ".center(25, "-"))
    if usage_logging in ("per_model", "verbose"):
        for model, totals in usage_totals_by_model.items():
            print_usage_summary(f"Model: {model}", totals)

    grand_totals = UsageInfo()
    for usage in usage_totals_by_model.values():
        grand_totals.add(usage)

    print_usage_summary("Total:", grand_totals)
