from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from myteam.workflow import run_agent
from myteam.workflow.models import StepResult

WORKFLOW_AGENT = "codex"


def main(feature_request: str | None = None) -> dict[str, Any]:
    request = collect_feature_request(feature_request)
    branch = require_feature_branch()

    interface = update_interface_doc(request, branch)
    plan = design_feature(request, interface, branch)
    framework = refactor_framework(plan)
    tests = update_tests(plan, framework)
    implementation = implement_feature(plan, framework, tests)
    conclusion = conclude_feature(plan, implementation)

    print_summary(conclusion)
    return conclusion


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


def collect_feature_request(feature_request: str | None = None) -> dict[str, Any]:
    return run_step(
        input={"feature_request": feature_request} if feature_request is not None else None,
        prompt=(
            "Understand the feature request. Ask clarifying questions if needed. "
            "Return an implementation-ready summary, explicit non-goals, unresolved "
            "questions, and whether the request is ready for interface-document work."
        ),
        output={
            "summary": "",
            "intended_behavior": "",
            "non_goals": "",
            "open_questions": "",
            "ready": False,
        },
    )


def update_interface_doc(request: dict[str, Any], branch: str) -> dict[str, Any]:
    return run_step(
        input={"request": request, "branch": branch},
        prompt=(
            "Read src/governing_docs/application_interface.md. Update it to describe "
            "the requested behavior. Review the change with the user. Commit the "
            "interface-document change only after approval."
        ),
        output={
            "interface_changes": "",
            "approved": False,
            "commit": "",
        },
    )


def design_feature(
    request: dict[str, Any],
    interface: dict[str, Any],
    branch: str,
) -> dict[str, Any]:
    return run_step(
        input={"request": request, "interface": interface, "branch": branch},
        prompt=(
            "Run `myteam get skill development/feature-pipeline/framework-oriented-design`. "
            "Inspect the relevant code. Write src/governing_docs/feature_plans/<branch>.md "
            "with Framework refactor and Feature addition sections. Get user approval "
            "on the feature plan, then commit it."
        ),
        output={
            "plan_path": "",
            "framework_refactor": "",
            "feature_addition": "",
            "approved": False,
            "commit": "",
        },
    )


def refactor_framework(plan: dict[str, Any]) -> dict[str, Any]:
    return run_step(
        input=plan,
        prompt=(
            "Apply only the feature-neutral framework refactor from the approved plan. "
            "The existing tests should still pass. Explain how the refactor makes the "
            "feature implementation simpler. Get user approval, then commit."
        ),
        output={
            "changes": "",
            "test_results": "",
            "approved": False,
            "commit": "",
        },
    )


def update_tests(plan: dict[str, Any], framework: dict[str, Any]) -> dict[str, Any]:
    return run_step(
        input={"plan": plan, "framework": framework},
        prompt=(
            "Run `myteam get skill development/testing`. Update the tests to match "
            "the approved interface document before implementing the feature. Explain "
            "how the tests prove the interface behavior. Get user approval, then commit."
        ),
        output={
            "test_changes": "",
            "coverage_rationale": "",
            "approved": False,
            "commit": "",
        },
    )


def implement_feature(
    plan: dict[str, Any],
    framework: dict[str, Any],
    tests: dict[str, Any],
) -> dict[str, Any]:
    return run_step(
        input={"plan": plan, "framework": framework, "tests": tests},
        prompt=(
            "Implement the feature according to the approved plan and updated tests. "
            "Run the relevant tests. Review the implementation with the user. Commit "
            "only after approval."
        ),
        output={
            "changes": "",
            "test_results": "",
            "approved": False,
            "commit": "",
            "remaining_work": "",
        },
    )


def conclude_feature(
    plan: dict[str, Any],
    implementation: dict[str, Any],
) -> dict[str, Any]:
    review_state: dict[str, Any] = {
        "plan": plan,
        "implementation": implementation,
        "attempt": 0,
    }

    while True:
        review_state["attempt"] += 1
        code_review, myteam_update = run_parallel_final_reviews(review_state)

        if is_true(code_review["ready"]):
            break

        review_state["latest_code_review"] = code_review
        review_state["implementation"] = address_code_review_findings(review_state)

    return run_conclusion_step(
        plan=plan,
        implementation=review_state["implementation"],
        code_review=code_review,
        myteam_update=myteam_update,
    )


def run_parallel_final_reviews(
    state: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    with ThreadPoolExecutor(max_workers=2) as executor:
        code_review_future = executor.submit(run_code_linter, state)
        myteam_update_future = executor.submit(run_project_myteam_update, state)

        code_review = code_review_future.result()
        myteam_update = myteam_update_future.result()

    return code_review, myteam_update


def run_code_linter(state: dict[str, Any]) -> dict[str, Any]:
    return run_step(
        input=state,
        prompt=(
            "Run `myteam get role development/feature-pipeline/code-linter`. "
            "Please confirm that this branch is ready. Do not make code changes. "
            "Return findings, readiness, and any follow-up work."
        ),
        output={
            "findings": "",
            "ready": False,
            "follow_up_work": "",
        },
    )


def run_project_myteam_update(state: dict[str, Any]) -> dict[str, Any]:
    return run_step(
        input=state,
        prompt=(
            "Run `myteam get role development/feature-pipeline/project-myteam-update`. "
            "Please identify and correct any needed migrations in .myteam. Return "
            "whether migration work was needed, what changed, and any migration doc path."
        ),
        output={
            "migration_needed": False,
            "changes": "",
            "migration_doc": "",
        },
    )


def address_code_review_findings(state: dict[str, Any]) -> dict[str, Any]:
    return run_step(
        input=state,
        prompt=(
            "Address the code-linter findings. Make only the needed changes, run "
            "relevant tests, and commit if changes were made. After this step, the "
            "final review pair will run again."
        ),
        output={
            "changes": "",
            "test_results": "",
            "commit": "",
            "remaining_work": "",
        },
    )


def run_conclusion_step(
    *,
    plan: dict[str, Any],
    implementation: dict[str, Any],
    code_review: dict[str, Any],
    myteam_update: dict[str, Any],
) -> dict[str, Any]:
    return run_step(
        input={
            "plan": plan,
            "implementation": implementation,
            "code_review": code_review,
            "myteam_update": myteam_update,
        },
        prompt=(
            "Run `myteam get skill development/feature-pipeline/conclusion`. "
            "Complete the semi-final/final commit logic, version bump, changelog, "
            "README/docs updates, completed backlog movement, and final readiness report."
        ),
        output={
            "version": "",
            "changelog": "",
            "docs": "",
            "completed_backlog": "",
            "final_commit": "",
            "ready_to_push": False,
        },
    )


def is_true(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"


def print_summary(result: dict[str, Any]) -> None:
    print(result)


if __name__ == "__main__":
    main()
