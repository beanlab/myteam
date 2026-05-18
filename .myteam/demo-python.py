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
    print(ranking.output)
    return ranking

def generate_poems() -> dict[str, Any]:
    return run_agent(
        agent=WORKFLOW_AGENT,
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
    return run_agent(
        agent=WORKFLOW_AGENT,
        input=poems,
        prompt=(
            "Rank the provided poems by how well each poem captures the essence of its style"
        ),
        output={
            "best_poem": "the poem that was chosen as the winner",
            "reasons": "why that poem was chosen over the others",
        },
    )


if __name__ == "__main__":
    main()
