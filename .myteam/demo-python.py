#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

from myteam.workflow import AgentContext
from myteam.workflow import StepResult

WORKFLOW_AGENT = "codex"


def main() -> dict[str, Any]:
    with AgentContext(usage_logging="verbose") as ctx:
        poems = generate_poems(ctx)
        ranking = rank_poems(ctx, poems.output)
        print(ranking.output)
        return ranking


def generate_poems(ctx: AgentContext) -> StepResult:
    return ctx.run_agent(
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


def rank_poems(ctx: AgentContext, poems: dict[str, Any]) -> StepResult:
    return ctx.run_agent(
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
