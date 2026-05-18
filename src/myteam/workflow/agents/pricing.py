from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache(maxsize=1)
def load_pricing() -> dict[str, dict[str, float]]:
    pricing_path = Path(__file__).with_name("pricing.yaml")
    try:
        loaded = yaml.safe_load(pricing_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(loaded, dict):
        return {}

    pricing = loaded.get("gpt_pricing")
    if not isinstance(pricing, dict):
        return {}

    normalized: dict[str, dict[str, float]] = {}
    for model, model_pricing in pricing.items():
        if not isinstance(model, str) or not isinstance(model_pricing, dict):
            continue
        try:
            normalized[model] = {
                "input_per_million": float(model_pricing["input_per_million"]),
                "cached_input_per_million": float(model_pricing["cached_input_per_million"]),
                "output_per_million": float(model_pricing["output_per_million"]),
            }
        except (KeyError, TypeError, ValueError):
            continue
    return normalized


def estimate_usage_cost(
    model: str,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
) -> float:
    model_pricing = load_pricing().get(model)
    if model_pricing is None:
        return 0.0

    non_cached_input_tokens = max(input_tokens - cached_input_tokens, 0)
    return (
        non_cached_input_tokens * model_pricing["input_per_million"]
        + cached_input_tokens * model_pricing["cached_input_per_million"]
        + output_tokens * model_pricing["output_per_million"]
    ) / 1_000_000
