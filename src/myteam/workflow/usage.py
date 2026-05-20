from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .agents.runtime import AgentRuntimeConfig
from .models import UsageInfo

if TYPE_CHECKING:
    from .steps import _ExecutionOutcome


@dataclass
class UsageTotals:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0

    def add(self, usage: UsageInfo) -> None:
        self.input_tokens += usage.input_tokens
        self.cached_input_tokens += usage.cached_input_tokens
        self.output_tokens += usage.output_tokens
        self.reasoning_output_tokens += usage.reasoning_output_tokens
        self.total_tokens += usage.total_tokens
        self.estimated_cost += usage.estimated_cost


@dataclass(frozen=True)
class UsageTrackingResult:
    usage: UsageInfo | None
    usage_state: str
    usage_error_message: str | None


class UsageTracker:
    """Own usage resolution, aggregation, and reporting for workflow steps."""

    _COLLECTIBLE_FAILURE_TYPES = {
        "completion_missing",
        "output_validation",
        "session_discovery",
        "timeout",
    }

    def __init__(self) -> None:
        self._usage_totals_by_model: dict[str, UsageTotals] = {}

    def resolve_for_outcome(self, outcome: _ExecutionOutcome) -> UsageTrackingResult:
        agent_config = outcome.agent_config
        if agent_config is None:
            return UsageTrackingResult(None, "not_attempted", None)

        if not self._should_collect_for_outcome(outcome):
            return UsageTrackingResult(None, "not_attempted", None)

        session_path = outcome.session_path
        if session_path is None:
            session_path = resolve_usage_session_path(
                agent_config=agent_config,
                nonce=outcome.nonce,
            )
        if session_path is None:
            return UsageTrackingResult(None, "not_attempted", None)

        usage, usage_state, usage_error_message = resolve_usage_tracking(
            agent_config=agent_config,
            session_path=session_path,
        )
        return UsageTrackingResult(
            usage=usage,
            usage_state=usage_state,
            usage_error_message=usage_error_message,
        )

    def record(self, usage: UsageInfo | None) -> None:
        if usage is None:
            return
        totals = self._usage_totals_by_model.get(usage.model)
        if totals is None:
            totals = UsageTotals()
            self._usage_totals_by_model[usage.model] = totals
        totals.add(usage)

    def print_step(self, usage: UsageInfo | None) -> None:
        if usage is None:
            return
        print_usage_summary(usage)

    def print_totals(self) -> None:
        if not self._usage_totals_by_model:
            return
        print_aggregated_usage_summary(self._usage_totals_by_model)

    def _should_collect_for_outcome(self, outcome: _ExecutionOutcome) -> bool:
        if outcome.status == "completed":
            return True
        return outcome.error_type in self._COLLECTIBLE_FAILURE_TYPES


def resolve_usage_tracking(
    *,
    agent_config: AgentRuntimeConfig,
    session_path: Path,
) -> tuple[UsageInfo | None, str, str | None]:
    if agent_config.get_usage_info is None:
        return (
            None,
            "no_get_usage_info_implemented",
            "workflow agent config does not implement get_usage_info",
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


def print_usage_summary(usage: UsageInfo) -> None:
    print("Usage:")
    print(f"  Model: {usage.model}")
    print(f"  Input: {usage.input_tokens}")
    print(f"  Cached Input: {usage.cached_input_tokens}")
    print(f"  Output: {usage.output_tokens}")
    print(f"  Reasoning: {usage.reasoning_output_tokens}")
    print(f"  Total: {usage.total_tokens}")
    print(f"  Cost: ${usage.estimated_cost:.4f}")


def print_aggregated_usage_summary(usage_totals_by_model: dict[str, UsageTotals]) -> None:
    print("Usage Summary:")
    for model, totals in usage_totals_by_model.items():
        print(f"  Model: {model}")
        print(f"    Input: {totals.input_tokens}")
        print(f"    Cached Input: {totals.cached_input_tokens}")
        print(f"    Output: {totals.output_tokens}")
        print(f"    Reasoning: {totals.reasoning_output_tokens}")
        print(f"    Total: {totals.total_tokens}")
        print(f"    Cost: ${totals.estimated_cost:.4f}")

    grand_totals = UsageTotals()
    for totals in usage_totals_by_model.values():
        grand_totals.input_tokens += totals.input_tokens
        grand_totals.cached_input_tokens += totals.cached_input_tokens
        grand_totals.output_tokens += totals.output_tokens
        grand_totals.reasoning_output_tokens += totals.reasoning_output_tokens
        grand_totals.total_tokens += totals.total_tokens
        grand_totals.estimated_cost += totals.estimated_cost

    print("Grand Totals:")
    print(f"  Input: {grand_totals.input_tokens}")
    print(f"  Cached Input: {grand_totals.cached_input_tokens}")
    print(f"  Output: {grand_totals.output_tokens}")
    print(f"  Total: {grand_totals.total_tokens}")
    print(f"  Cost: ${grand_totals.estimated_cost:.4f}")
