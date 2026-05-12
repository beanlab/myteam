from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

LOCAL_ROOT = Path(
    os.environ.get("MYTEAM_PROJECT_ROOT", Path(__file__).resolve().parents[1])
).resolve()
REPO_ROOT = LOCAL_ROOT.parent
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
    "Waiting for Review": "f576f05d",
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

STEP_ALIASES = {
    "scenarios": "scenario_conversation",
    "design": "implement-conversation",
}

PAIRED_ARTIFACT_STEP = {
    "high_level_design_conversation": "high_level_design_artifact",
    "scenario_conversation": "scenario_artifact",
    "implement-conversation": "implement",
}

ALLOWED_NEXT_STEPS = {
    "high_level_design_conversation": (
        "high_level_design_conversation",
        "high_level_design_artifact",
    ),
    "high_level_design_artifact": (
        "high_level_design_conversation",
        "scenario_conversation",
    ),
    "scenario_conversation": ("scenario_conversation", "scenario_artifact"),
    "scenario_artifact": (
        "high_level_design_conversation",
        "scenario_conversation",
        "implement-conversation",
    ),
    "implement-conversation": (
        "implement-conversation",
        "implement",
    ),
    "implement": (
        "high_level_design_conversation",
        "scenario_conversation",
        "implement-conversation",
        "implement",
        "review",
    ),
    "review": (
        "high_level_design_conversation",
        "scenario_conversation",
        "implement-conversation",
        "implement",
        "review",
        "wrap_up",
    ),
}

START_STEPS = (
    "high_level_design_conversation",
    "scenario_conversation",
    "implement-conversation",
    "implement",
    "review",
    "scenarios",
    "design",
)


def main(feature_request: str | None = None) -> dict[str, Any]:
    require_feature_branch()

    state = backlog_step(feature_request)
    state = run_looping_steps(state)
    state = wrap_up_step(state)
    state = complete_step(state)

    print_summary(state)
    return state


def run_looping_steps(state: dict[str, Any]) -> dict[str, Any]:
    start_step = state.get("start_step", "scenarios")
    if not isinstance(start_step, str):
        raise RuntimeError("Workflow state start_step must be a string.")
    validate_start_step(start_step)

    step_name = normalize_step_name(start_step)
    while step_name != "wrap_up":
        if step_name == "high_level_design_conversation":
            result = high_level_design_conversation_step(state)
        elif step_name == "high_level_design_artifact":
            result = high_level_design_artifact_step(state)
        elif step_name == "scenario_conversation":
            result = scenario_conversation_step(state)
        elif step_name == "scenario_artifact":
            result = scenario_artifact_step(state)
        elif step_name == "implement-conversation":
            result = implement_conversation_step(state)
        elif step_name == "implement":
            result = implement_step(state)
        elif step_name == "review":
            result = review_step(state)
        else:
            raise RuntimeError(f"Unknown workflow step: {step_name}")

        next_step = result.get("next_step")
        if not isinstance(next_step, str):
            raise RuntimeError(f"Step '{step_name}' did not return next_step.")

        next_step = normalize_step_name(next_step)
        validate_next_step(step_name, next_step, result)
        state = merge_issue_state(state, result)
        step_name = next_step

    return state


def run_step(
        *,
        prompt: str,
        output: dict[str, Any],
        input: dict[str, Any],
        agent: str = WORKFLOW_AGENT,
        session_id: str | None = None,
) -> dict[str, Any]:
    result = run_agent(
        agent=agent,
        input=input,
        output=output,
        prompt=prompt,
        session_id=session_id,
    )
    return require_completed(result)


def require_completed(result: StepResult) -> dict[str, Any]:
    if result.status != "completed":
        raise RuntimeError(f"{result.error_type}: {result.error_message}")
    if not isinstance(result.output, dict):
        raise RuntimeError("Workflow step completed without a mapping output.")
    output = dict(result.output)
    if result.session_id and "session_id" not in output:
        output["session_id"] = result.session_id
    return output


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
        prompt="Your role is 'development-workflow/backlog'.",
        output=issue_output(
            backlog_summary="Short summary of the selected or created backlog issue.",
            start_step=(
                "high_level_design_conversation, scenario_conversation, "
                "implement-conversation, implement, or review"
            ),
        ),
    )


def high_level_design_conversation_step(state: dict[str, Any]) -> dict[str, Any]:
    return run_step(
        input=with_issue_sections(state),
        prompt="""Your role is 'development-workflow/high-level-design-conversation'.  You **MUST** obtain explicit approval from the user before calling the workflow-result command.""",
        output=planning_conversation_output(
            next_step="high_level_design_conversation or high_level_design_artifact",
        ),
    )


def high_level_design_artifact_step(state: dict[str, Any]) -> dict[str, Any]:
    return run_step(
        input=with_issue_sections(state),
        prompt="Your role is 'development-workflow/high-level-design-artifact'.",
        output=issue_output(
            design_summary="Summary of design decisions recorded in the issue body.",
            next_step="high_level_design_conversation or scenario_conversation",
        ),
        session_id=require_session_id(state, "high-level design"),
    )


def scenario_conversation_step(state: dict[str, Any]) -> dict[str, Any]:
    return run_step(
        input=with_issue_sections(state),
        prompt="""Your role is 'development-workflow/scenario-conversation'. You **MUST** obtain explicit approval from the user before calling the workflow-result command.""",
        output=planning_conversation_output(
            next_step="scenario_conversation or scenario_artifact",
        ),
    )


def scenario_artifact_step(state: dict[str, Any]) -> dict[str, Any]:
    result = run_step(
        input=with_issue_sections(state),
        prompt="Your role is 'development-workflow/scenario-artifact'.",
        output=issue_output(
            scenarios_summary="Summary of scenario decisions recorded in the issue body.",
            next_step=(
                "high_level_design_conversation, scenario_conversation, "
                "or implement-conversation"
            ),
        ),
        session_id=require_session_id(state, "scenario"),
    )
    set_project_status(result, "Ready")
    return result


def implement_conversation_step(state: dict[str, Any]) -> dict[str, Any]:
    return run_step(
        input=with_issue_sections(state),
        prompt="""Your role is 'development-workflow/implement-conversation'. You **MUST** obtain explicit approval from the user before calling the workflow-result command.""",
        output=planning_conversation_output(
            next_step="implement-conversation or implement",
        ),
    )


def implement_step(state: dict[str, Any]) -> dict[str, Any]:
    set_project_status(state, "In progress")
    result = run_step(
        input=with_issue_sections(state),
        prompt="Your role is 'development-workflow/implement'.",
        output=issue_output(
            implementation_summary=(
                "Approved implementation plan recorded and implementation completed."
            ),
            next_step=(
                "high_level_design_conversation, scenario_conversation, "
                "implement-conversation, implement, or review"
            ),
        ),
        session_id=require_session_id(state, "implement"),
    )
    return result


def review_step(state: dict[str, Any]) -> dict[str, Any]:
    return run_step(
        input=with_issue_sections(state),
        prompt="Your role is 'development-workflow/review'.",
        output=issue_output(
            review_summary="Summary of review findings recorded in the issue body.",
            ready=False,
            next_step="scenarios, design, implement, review, or wrap_up",
        ),
    )


def wrap_up_step(state: dict[str, Any]) -> dict[str, Any]:
    return run_step(
        input=with_issue_sections(state),
        prompt="Your role is 'development-workflow/wrap-up'.",
        output=issue_output(
            wrap_up_summary="Summary of final wrap-up work recorded in the issue body.",
            ready_to_complete=False,
        ),
    )


def complete_step(state: dict[str, Any]) -> dict[str, Any]:
    result = run_step(
        input=with_issue_sections(state),
        prompt="Your role is 'development-workflow/complete'.",
        output=issue_output(
            pr_url="Pull request URL.",
            completion_summary="Summary of completion state recorded in the issue body.",
        ),
    )
    set_project_status(result, "Waiting for Review")
    return merge_issue_state(state, result)


def issue_output(**extra: Any) -> dict[str, Any]:
    output = {
        "issue_number": "",
        "issue_id": "",
        "project_item_id": "",
    }
    output.update(extra)
    return output


def planning_conversation_output(*, next_step: str) -> dict[str, Any]:
    return issue_output(
        session_id="Agent session ID for the approved planning conversation.",
        approved=False,
        summary="Concise summary of the current planning conversation.",
        next_step=next_step,
    )


def with_issue_sections(state: dict[str, Any]) -> dict[str, Any]:
    merged = dict(state)
    merged["required_issue_sections"] = list(ISSUE_SECTIONS)
    return merged


def merge_issue_state(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    merged = dict(state)
    merged.update(result)
    return merged


def normalize_step_name(step_name: str) -> str:
    return STEP_ALIASES.get(step_name, step_name)


def validate_next_step(
        current_step: str,
        next_step: str,
        result: dict[str, Any],
) -> None:
    allowed = allowed_next_steps(current_step)
    if next_step not in allowed:
        allowed_text = ", ".join(allowed)
        raise RuntimeError(
            f"Step '{current_step}' cannot choose next_step '{next_step}'. "
            f"Allowed values: {allowed_text}."
        )
    paired_artifact = PAIRED_ARTIFACT_STEP.get(current_step)
    if paired_artifact is None:
        return
    approved = result.get("approved") is True
    if next_step == paired_artifact and not approved:
        raise RuntimeError(
            f"Step '{current_step}' cannot advance to '{next_step}' without approval."
        )
    if approved and next_step != paired_artifact:
        raise RuntimeError(
            f"Step '{current_step}' recorded approval but did not advance to "
            f"'{paired_artifact}'."
        )


def validate_start_step(start_step: str) -> None:
    allowed = allowed_start_steps()
    normalized_allowed = tuple(normalize_step_name(step) for step in allowed)
    if normalize_step_name(start_step) not in normalized_allowed:
        allowed_text = ", ".join(allowed)
        raise RuntimeError(
            f"Workflow cannot start at step '{start_step}'. "
            f"Allowed values: {allowed_text}."
        )


def allowed_start_steps() -> tuple[str, ...]:
    return START_STEPS


def allowed_next_steps(current_step: str) -> tuple[str, ...]:
    if current_step not in ALLOWED_NEXT_STEPS:
        raise RuntimeError(f"Step '{current_step}' does not support next_step.")
    return ALLOWED_NEXT_STEPS[current_step]


def require_session_id(state: dict[str, Any], phase: str) -> str:
    session_id = state.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise RuntimeError(f"Cannot write {phase} artifact without session_id.")
    return session_id


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
