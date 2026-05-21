from __future__ import annotations

import json
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
            "the changelog is updated, also update the .toml file as needed",
            "",
            "Also draft a PR body for the overall changes on this branch and return",
            "it as output",
        ),
        input={
            "git_diff": git_diff,
        },
        output={
            "commit_message": "brief, informative commit message for the documentation changes",
            "pr_body": "PR body message containing sections: Overview, Black-box level changes, File-level changes",
        },
    )


def conclude(ctx: AgentContext, pr_body: str) -> StepResult:
    i = list_github_issues()
    i["pr_body"] = pr_body
    return ctx.run_agent(
        agent=AGENT,
        model=MODEL,
        input=i,
        prompt=(
            "Open a pull request for the current branch and write the PR body.",
            "Then update the issue body's Pull Request section with the PR URL and "
            "final status."
        ),
        output={
            "pr_url": "pull request URL",
            "pr_body": "pull request body text",
            "issue_update": "summary of the issue body update",
            "ready_to_push": False,
        },
    )


def list_github_issues() -> dict:
    repo_root = Path(__file__).resolve().parents[1]
    project_items_raw = subprocess.check_output(
        [
            "gh",
            "project",
            "item-list",
            "13",
            "--owner",
            "beanlab",
            "--format",
            "json",
        ],
        text=True,
        cwd=repo_root,
    ).strip()
    issues_raw = subprocess.check_output(
        [
            "gh",
            "issue",
            "list",
            "--state",
            "all",
            "--limit",
            "100",
            "--json",
            "number,title,state,labels,url,updatedAt",
        ],
        text=True,
        cwd=repo_root,
    ).strip()

    project_items_data = json.loads(project_items_raw) if project_items_raw else {}
    project_items = (
        project_items_data.get("items", project_items_data)
        if isinstance(project_items_data, dict)
        else project_items_data
    )
    issues = json.loads(issues_raw) if issues_raw else []

    return {
            "project": {
                "owner": "beanlab",
                "number": 13,
                "items": project_items,
            },
            "issues": issues,
        }


def commit_changes(msg: str) -> str:
    """Commit the unstaged changes on the branch with the given message."""
    repo_root = Path(__file__).resolve().parents[1]
    subprocess.check_call(["git", "-C", str(repo_root), "add", "-A"])

    staged = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--cached", "--quiet"],
        check=False,
    )
    if staged.returncode == 0:
        return ""

    subprocess.check_call(["git", "-C", str(repo_root), "commit", "-m", msg])
    return subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
        text=True,
    ).strip()


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
        require_completion(conclude(ctx, review_result.output["pr_body"]))


if __name__ == "__main__":
    main()
