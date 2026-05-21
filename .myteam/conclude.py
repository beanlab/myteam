from __future__ import annotations

import json
import subprocess
from pathlib import Path

from myteam.workflow.steps import AgentContext
from myteam.workflow.models import StepResult

AGENT = "codex"
MODEL = "gpt-5.4-mini"


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
    untracked_files = subprocess.check_output(
        [
            "git",
            "-C",
            str(repo_root),
            "ls-files",
            "--others",
            "--exclude-standard",
        ],
        text=True,
    ).splitlines()
    untracked_sections = []
    for rel_path in sorted(path for path in untracked_files if path.strip()):
        file_path = repo_root / rel_path
        try:
            file_contents = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            file_contents = file_path.read_text(encoding="utf-8", errors="replace")
        untracked_sections.extend(
            [
                f"### {rel_path}",
                file_contents.rstrip(),
                "",
            ]
        )

    sections = [
        "## git status --short",
        status or "(clean)",
        "",
        "## git diff",
        diff or "(no tracked changes)",
    ]
    if untracked_sections:
        sections.extend(
            [
                "",
                "## untracked files",
                "",
                *untracked_sections,
            ]
        )
    return "\n".join(sections).rstrip()


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


def require_completion(result):
    if result.status != "completed" and result.error_type != 'completion_missing':
        raise RuntimeError(result.error_message)
    return result


def review_docs(ctx: AgentContext) -> StepResult:
    git_diff = get_branch_diff()
    return ctx.run_agent(
        agent=AGENT,
        model=MODEL,
        input={
            "git_diff": git_diff,
        },
        prompt=(
            "Review the current repository changes with emphasis on documentation.",
            "`application_interface.md, `CHANGELOG.md` (where applicable) and other",
            "documentation should accurately reflect the current project state",
            "",
            "The changelog should only contain significant user-facing changes. When"
            "the changelog is updated, also update the .toml file as needed",
            "",
            "Also draft a PR body for the overall changes on this branch and return",
            "it as output. Do not run tests",
        ),
        output={
            "commit_message": "brief, informative commit message for the documentation changes",
            "pr_body": "PR body message containing sections: Overview, Black-box level changes, File-level changes",
        },
    )

def review_myteam(ctx: AgentContext, pr_body: str) -> StepResult:
    """
    This reviews changes to the myteam src code and writes migration
    instructions if needed.
    For other projects, this step should evaluate the current `.myteam`
    roster for path references, etc. that may need to be updated.
    """
    return ctx.run_agent(
        agent=AGENT,
        model=MODEL,
        input={"pr_body": pr_body},
        prompt=(
            "Ensure that the existing `.myteam` tree stays up-to-date.",
            "",
            "- Review the pr_body and `CHANGELOG.md`. Were any templates modified?",
            "- Do any of the changes affect `.myteam` organization or structure?",
            "",
            "If so, create a document in `src/myteam/migrations/<version>.md` to",
            "document changes and provide careful instructions for how to migrate",
            "an existing `.myteam` folder and files to reflect the changes.",
            "The document will be used by our users to update their `.myteam` folders",
            "to the latest features / format.",
            "",
            "These instructions should be generic:",
            "they should NOT assume specific role or skill folders.",
            "They should simply describe the general changes needed to `load.py` or",
            "other files to match the new templates or assumptions.",
            "",
            "For example, if new content has been added to the AGENTS.md template,",
            "then that new content should be integrated into existing AGENTS.md files.",
            "",
            "Or, if a new function is available in `utils` and was included in the",
            "default role `load.py` template, then existing role `load.py` files",
            "should be updated to use this new utility.",
            "",
            "The migration instructions should clearly explain what the changes are",
            "and how those changes might be applied to existing structure.",
        ),
        output={
            "commit_message": "brief, informative commit message for the migration changes",
        }
    )


def conclude(ctx: AgentContext, pr_body: str) -> StepResult:
    i = list_github_issues()
    i["pr_body"] = pr_body
    return ctx.run_agent(
        agent=AGENT,
        model=MODEL,
        input=i,
        prompt=(
            "Open a pull request if a PR hasn't already been opened for the current",
            "branch and write/update the PR body.",
            "If an issue in the project is closed or related to the changes on",
            "this branch, mention it in the pr body as well.",
            "Then update the issue body's Pull Request section with the PR URL and",
            "final status.",
        ),
        output={
            "pr_url": "pull request URL",
            "pr_body": "summary of the pr body changes",
            "issue_update": "summary of the issue body update",
        },
    )


def main():
    with AgentContext(usage_logging="summary") as ctx:
        # review documetation
        review_result = require_completion(review_docs(ctx))
        commit_changes(review_result.output["commit_message"])

        # review myteam changes
        myteam_result = review_myteam(ctx, review_result.output["pr_body"])
        commit_changes(myteam_result.output["commit_message"])

        # open pr
        require_completion(conclude(ctx, review_result.output["pr_body"]))


if __name__ == "__main__":
    main()
