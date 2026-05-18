#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from myteam.workflow import run_agent
from myteam.workflow.models import StepResult

WORKFLOW_AGENT = "codex"


def main() -> dict[str, Any]:
    total_cost = 0
    poems = generate_poems()
    total_cost += poems.usage.estimated_cost
    ranking = rank_poems(poems.output)
    total_cost += ranking.usage.estimated_cost
    print(f"Total cost: ${total_cost:.4f}")
    print_summary(ranking.output)
    return ranking


def run_step(
    *,
    prompt: str,
    output: dict[str, Any],
    input: Any | None = None,
    agent: str = WORKFLOW_AGENT,
) -> dict[str, Any]:
    result = run_agent(
        agent=agent,
        input=input,
        output=output,
        prompt=prompt,
    )
    return require_completed(result)


def require_completed(result: StepResult) -> dict[str, Any]:
    if result.status != "completed":
        raise RuntimeError(f"{result.error_type}: {result.error_message}")
    if not isinstance(result.output, dict):
        raise RuntimeError("Workflow step completed without a mapping output.")
    return result


def generate_poems() -> dict[str, Any]:
    return run_step(
        prompt=(
            "Generate 3 poems on topics provided by the user. Ask them for the topics."
        ),
        output={
            "poem1": "a haiku",
            "poem2": "a limerick",
            "poem3": "a couplet",
        },
    )


def rank_poems(poems: dict[str, Any]) -> dict[str, Any]:
    return run_step(
        input=poems,
        prompt=(
            "Rank the provided poems by how well each poem captures the essence of its style"
        ),
        output={
            "best_poem": "the poem that was chosen as the winner",
            "reasons": "why that poem was chosen over the others",
        },
    )


def print_summary(result: dict[str, Any]) -> None:
    print(result)


if __name__ == "__main__":
    main()
