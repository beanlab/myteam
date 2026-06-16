"""
name: "Demo Python"
description: "This is a short demo of a multi-step task"
agent: codex
model:
output:
input:
interactive:
session_id:
fork:
extra_args:
usage_logging:
timeout:
"""

#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

from myteam.tasks import AgentContext, StepResult


def main() -> dict[str, Any]:
    with AgentContext(usage_logging="verbose") as ctx:
        poems = generate_poems(ctx)
        ranking = rank_poems(ctx, poems.output)
        print(ranking.output)
        return ranking


def generate_poems(ctx: AgentContext) -> StepResult:
    return ctx.run_agent(
        prompt=(
            "Generate 3 poems on topics provided by the user. Ask them for the topics."
        ),
        output={
            "poem1": "a haiku",
            "poem2": "a limerick",
            "poem3": "a couplet",
        },
    )


def rank_poems(ctx: AgentContext, poems: dict[str, Any]) -> StepResult:
    return ctx.run_agent(
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
