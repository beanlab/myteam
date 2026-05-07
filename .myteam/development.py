from __future__ import annotations

import json
import subprocess
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

PROJECT_OWNER = "beanlab"
PROJECT_NUMBER = "13"
PROJECT_ID = "PVT_kwDOCA0Mqs4BW0Oo"
STATUS_FIELD_ID = "PVTSSF_lADOCA0Mqs4BW0OozhSFeKU"
STATUS_OPTIONS = {
    "Backlog": "f75ad846",
    "Ready": "a6761bea",
    "In progress": "47fc9ee4",
    "Done": "98236657",
}

ISSUE_SECTIONS = (
    "Details",
    "Out-of-scope",
    "Dependencies",
    "Scenarios",
    "Design",
    "Implementation",
    "Review",
    "Wrap Up",
    "Pull Request",
)

FORWARD_STEP = {
    "scenarios": "design",
    "design": "implement",
    "implement": "review",
    "review": "wrap_up",
}

BACKWARD_LIMIT = {
    "scenarios": (),
    "design": ("scenarios",),
    "implement": ("scenarios", "design"),
    "review": ("scenarios", "design", "implement"),
}


def main(feature_request: str | None = None) -> dict[str, Any]:
    require_feature_branch()

    state = backlog_step(feature_request)
    state = run_looping_steps(state)
    state = wrap_up_step(state)
    state = complete_step(state)

    print_summary(state)
    return state


def run_looping_steps(state: dict[str, Any]) -> dict[str, Any]:
    step_name = "scenarios"
    while step_name != "wrap_up":
        if step_name == "scenarios":
            result = scenarios_step(state)
        elif step_name == "design":
            result = design_step(state)
        elif step_name == "implement":
            result = implement_step(state)
        elif step_name == "review":
            result = review_step(state)
        else:
            raise RuntimeError(f"Unknown workflow step: {step_name}")

        next_step = result.get("next_step")
        if not isinstance(next_step, str):
            raise RuntimeError(f"Step '{step_name}' did not return next_step.")

        validate_next_step(step_name, next_step)
        state = merge_issue_state(state, result)
        step_name = next_step

    return state


def run_step(
    *,
    prompt: str,
    output: dict[str, Any],
    input: dict[str, Any],
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
    return result.output


def require_feature_branch() -> str:
    branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        text=True,
    ).strip()
    if branch == "main":
        raise RuntimeError(
            "Start a feature branch before running the development workflow."
        )
    return branch


def backlog_step(feature_request: str | None = None) -> dict[str, Any]:
    return run_step(
        input={
            "feature_request": feature_request,
            "issue_number": "",
            "issue_id": "",
            "project_item_id": "",
            "project_owner": PROJECT_OWNER,
            "project_number": PROJECT_NUMBER,
            "required_issue_sections": list(ISSUE_SECTIONS),
        },
        prompt=(
            "Run `myteam get skill project-management/backlog`. Identify the GitHub issue for this "
            "development workflow from the Bean Lab project, or create one if needed. "
            "Edit the issue body so it contains the required workflow sections. Return "
            "the issue identifiers and a concise backlog summary."
        ),
        output=issue_output(
            backlog_summary="Short summary of the selected or created backlog issue.",
        ),
    )


def scenarios_step(state: dict[str, Any]) -> dict[str, Any]:
    return run_step(
        input=with_issue_sections(state),
        prompt=(
            "Update the issue body's Scenarios section. Write externally visible "
            "behavior scenarios using context, action, and outcome. Return next_step "
            "as scenarios if more scenario work is needed, otherwise design."
        ),
        output=issue_output(
            scenarios_summary="Summary of scenario decisions recorded in the issue body.",
            next_step="scenarios or design",
        ),
    )


def design_step(state: dict[str, Any]) -> dict[str, Any]:
    result = run_step(
        input=with_issue_sections(state),
        prompt=(
            "Load `development/feature-pipeline/framework-oriented-design`. Plan the "
            "feature from the issue scenarios. Edit the issue body's Design section "
            "with the implementation plan and any framework-oriented design decisions. "
            "Return next_step as scenarios, design, or implement."
        ),
        output=issue_output(
            design_summary="Summary of design decisions recorded in the issue body.",
            next_step="scenarios, design, or implement",
        ),
    )
    set_project_status(result, "Ready")
    return result


def implement_step(state: dict[str, Any]) -> dict[str, Any]:
    set_project_status(state, "In progress")
    return run_step(
        input=with_issue_sections(state),
        prompt=(
            "Implement the feature according to the issue body's Scenarios and Design "
            "sections. Run relevant tests. Edit the issue body's Implementation section "
            "with the changes and test results. Return next_step as scenarios, design, "
            "implement, or review."
        ),
        output=issue_output(
            implementation_summary="Summary of implementation work recorded in the issue body.",
            test_results="Relevant test command results.",
            next_step="scenarios, design, implement, or review",
        ),
    )


def review_step(state: dict[str, Any]) -> dict[str, Any]:
    return run_step(
        input=with_issue_sections(state),
        prompt=(
            "Review the implementation against the issue body's Scenarios and Design "
            "sections. Also apply framework-oriented design and code-linter guidance. "
            "Edit the issue body's Review section with findings and readiness. Return "
            "next_step as scenarios, design, implement, review, or wrap_up."
        ),
        output=issue_output(
            review_summary="Summary of review findings recorded in the issue body.",
            ready=False,
            next_step="scenarios, design, implement, review, or wrap_up",
        ),
    )


def wrap_up_step(state: dict[str, Any]) -> dict[str, Any]:
    return run_step(
        input=with_issue_sections(state),
        prompt=(
            "Load `development/feature-pipeline/conclusion`. Complete the MVP wrap-up: "
            "final checks, version decision, changelog, README/docs updates, and "
            "project-myteam-update review when relevant. Edit the issue body's Wrap Up "
            "section with the final readiness state."
        ),
        output=issue_output(
            wrap_up_summary="Summary of final wrap-up work recorded in the issue body.",
            ready_to_complete=False,
        ),
    )


def complete_step(state: dict[str, Any]) -> dict[str, Any]:
    result = run_step(
        input=with_issue_sections(state),
        prompt=(
            "Open a pull request for the current branch. Link the issue in the PR body. "
            "Edit the issue body's Pull Request section with the PR URL and final status."
        ),
        output=issue_output(
            pr_url="Pull request URL.",
            completion_summary="Summary of completion state recorded in the issue body.",
        ),
    )
    set_project_status(result, "Done")
    return merge_issue_state(state, result)


def issue_output(**extra: Any) -> dict[str, Any]:
    output = {
        "issue_number": "",
        "issue_id": "",
        "project_item_id": "",
    }
    output.update(extra)
    return output


def with_issue_sections(state: dict[str, Any]) -> dict[str, Any]:
    merged = dict(state)
    merged["required_issue_sections"] = list(ISSUE_SECTIONS)
    return merged


def merge_issue_state(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    merged = dict(state)
    merged.update(result)
    return merged


def validate_next_step(current_step: str, next_step: str) -> None:
    allowed = allowed_next_steps(current_step)
    if next_step not in allowed:
        allowed_text = ", ".join(allowed)
        raise RuntimeError(
            f"Step '{current_step}' cannot choose next_step '{next_step}'. "
            f"Allowed values: {allowed_text}."
        )


def allowed_next_steps(current_step: str) -> tuple[str, ...]:
    if current_step not in FORWARD_STEP:
        raise RuntimeError(f"Step '{current_step}' does not support next_step.")
    return (*BACKWARD_LIMIT[current_step], current_step, FORWARD_STEP[current_step])


def ensure_issue_sections(body: str) -> str:
    updated = body.rstrip()
    for section in ISSUE_SECTIONS:
        heading = f"## {section}"
        if not has_markdown_heading(updated, heading):
            updated = f"{updated}\n\n{heading}\n\nTBD." if updated else f"{heading}\n\nTBD."
    return f"{updated}\n"


def has_markdown_heading(body: str, heading: str) -> bool:
    return any(line.strip() == heading for line in body.splitlines())


def set_project_status(state: dict[str, Any], status: str) -> None:
    project_item_id = state.get("project_item_id")
    if not project_item_id:
        raise RuntimeError("Cannot update project status without project_item_id.")
    option_id = STATUS_OPTIONS[status]
    subprocess.run(
        [
            "gh",
            "project",
            "item-edit",
            "--id",
            str(project_item_id),
            "--project-id",
            PROJECT_ID,
            "--field-id",
            STATUS_FIELD_ID,
            "--single-select-option-id",
            option_id,
        ],
        check=True,
    )


def print_summary(result: dict[str, Any]) -> None:
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
