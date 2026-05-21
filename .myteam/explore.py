from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

from myteam.workflow.models import StepResult
from myteam.workflow.steps import AgentContext

AGENT = "codex"
MODEL = "gpt-5.4-mini"
PROJECT_SETTINGS = {
    "owner": "beanlab",
    "number": 13,
    "project_id": "PVT_kwDOCA0Mqs4BW0Oo",
    "priority_field_id": "PVTSSF_lADOCA0Mqs4BW0OozhSFeN8",
    "priority_options": {
        "P0": "79628723",
        "P1": "0a877460",
        "P2": "da944a9c",
    },
}


def require_completion(result):
    if result.status != "completed" and result.error_type != "completion_missing":
        raise RuntimeError(result.error_message)
    return result


def explore(ctx: AgentContext) -> StepResult:
    return ctx.run_agent(
        AGENT=AGENT,
        model=MODEL,
        prompt="",
        output={},
    )


def summarize_issue(ctx: AgentContext, transcript) -> StepResult:
    return ctx.run_agent(
        AGENT=AGENT,
        model=MODEL,
        input={"transcript": transcript},
        prompt="",
        output={
            "issue_title": "the issue title",
            "issue_type": "either 'Touch Code' or 'null'",
            "issue_body": "the issue body",
        },
    )


def create_issue(title: str, type: Literal["Touch Code", "Task"], body: str) -> str:
    repo_root = Path(__file__).resolve().parents[1]

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        handle.write(body.rstrip() + "\n")
        body_path = handle.name

    try:
        issue_url = subprocess.check_output(
            [
                "gh",
                "issue",
                "create",
                "--title",
                title,
                "--body-file",
                body_path,
            ],
            text=True,
            cwd=repo_root,
        ).strip()

        _set_issue_type(repo_root, issue_url, type)

        try:
            subprocess.check_call(
                [
                    "gh",
                    "project",
                    "item-add",
                    str(PROJECT_SETTINGS["number"]),
                    "--owner",
                    PROJECT_SETTINGS["owner"],
                    "--url",
                    issue_url,
                ],
                cwd=repo_root,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"Issue created at {issue_url}, but adding it to the project failed."
            ) from exc

        return issue_url
    finally:
        Path(body_path).unlink(missing_ok=True)


def _set_issue_type(repo_root: Path, issue_url: str, issue_type_name: str) -> None:
    issue_types_raw = subprocess.check_output(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            'query=query { repository(owner:"beanlab", name:"myteam") { issueTypes(first:20) { nodes { id name } } } }',
        ],
        text=True,
        cwd=repo_root,
    ).strip()
    issue_types_data = json.loads(issue_types_raw) if issue_types_raw else {}
    nodes = (
        issue_types_data.get("data", {})
        .get("repository", {})
        .get("issueTypes", {})
        .get("nodes", [])
    )
    issue_type_id = next(
        (node["id"] for node in nodes if node.get("name") == issue_type_name),
        None,
    )
    if not issue_type_id:
        raise RuntimeError(f"Could not find GitHub issue type '{issue_type_name}'.")

    issue_node_raw = subprocess.check_output(
        [
            "gh",
            "issue",
            "view",
            issue_url,
            "--json",
            "id,number,url",
        ],
        text=True,
        cwd=repo_root,
    ).strip()
    issue_node = json.loads(issue_node_raw)
    subprocess.check_call(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            "query=mutation($id:ID!, $type:ID!) { updateIssue(input:{id:$id, issueTypeId:$type}) { issue { number issueType { name } } } }",
            "-f",
            f"id={issue_node['id']}",
            "-f",
            f"type={issue_type_id}",
        ],
        cwd=repo_root,
    )


def main():
    with AgentContext(
        usage_logging="summary",
        inactivity_timeout_seconds=900,
    ) as ctx:
        # this should be altered to run the explore process to clearly define the
        explore_result = require_completion(explore(ctx))
        summary_result = require_completion(summarize_issue(ctx, explore_result.transcript))
        create_issue(summary_result.output["issue_body"])
        # summarize the decisions and add to github project and return and output to conclude the workflow automatically
        pass


if __name__ == "__main__":
    main()
