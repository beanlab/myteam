from __future__ import annotations

import subprocess
from pathlib import Path

from myteam.workflow.steps import AgentContext
from myteam.workflow.models import StepResult

AGENT = "codex"
MODEL = "gpt-5.4-mini"


def review_docs(ctx: AgentContext) -> StepResult:
    git_diff = get_branch_diff()
    return ctx.run_agent(
        agent=AGENT,
        model=MODEL,
        prompt=(
            "Review the current repository changes with emphasis on documentation.",
            "`application_interface.md, `CHANGELOG.md` (where applicable) and other",
            "documentation should accurately reflect the current project state",
            "",
            "The changelog should only contain significant user-facing changes. When"
            "the changelog is updated, also update the .toml file as needed.",
        ),
        input={
            "git_diff": git_diff,
        },
        output={
            "commit_message": "brief, informative commit message for the documentation changes"
        },
    )


def conclude(ctx: AgentContext) -> StepResult:
    return ctx.run_agent(
        agent=AGENT,
        model=MODEL,
        prompt="Insert instructions for opening a PR with sections: overview, black-box level changes, and file-level changes",
        output={},
    )

def commit_changes(msg: str) -> str:
    """Commit the unstaged changes on the branch with the given message."""
    pass


def get_branch_diff() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    status = subprocess.check_output(
        ["git", "-C", str(repo_root), "status", "--short"],
        text=True,
    ).strip()
    diff = subprocess.check_output(
        ["git", "-C", str(repo_root), "diff", "--no-ext-diff", "--no-color"],
        text=True,
    ).strip()

    return "\n".join(
        [
            "## git status --short",
            status or "(clean)",
            "",
            "## git diff",
            diff or "(no tracked changes)",
        ]
    )


def require_completion(result):
    if result.status != "completed" and result.error_type != 'completion_missing':
        raise RuntimeError(result.error_message)
    return result


def main():
    with AgentContext(usage_logging="summary") as ctx:
        review_result = require_completion(review_docs(ctx))
        commit_changes(review_result.output["commit_message"])
        require_completion(conclude(ctx))


if __name__ == "__main__":
    main()
