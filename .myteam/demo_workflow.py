from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from myteam.workflow import execute_step
from myteam.workflow.models import StepResult

WORKFLOW_AGENT = "codex"


def _execute_required_step(step_definition: dict) -> StepResult:
    result = execute_step(
        agent=step_definition.get("agent"),
        input=step_definition.get("input"),
        output=step_definition["output"],
        prompt=step_definition["prompt"],
    )
    if result.status != "completed":
        raise RuntimeError(
            f"Workflow step failed with {result.error_type}: {result.error_message}"
        )
    return result

def feature_pipeline():
    plan_step = {
        "agent": WORKFLOW_AGENT,
        "output": {
            "feature_spec": "the feature request translated into an implementation-ready spec",
            "framework_changes": "framework refactors or extensions required before feature work begins",
            "implementation_slices": "an ordered list of small implementation slices",
            "test_plan": "tests that should exist before and after implementation"
        },
        "prompt": (
            "Plan the feature using `myteam get skill "
            "development/feature-pipeline/framework-oriented-design`. "
            "Produce a framework-oriented design that is ready to implement."
        )
    }
    plan_result = _execute_required_step(plan_step)

    framework_step = {
        "agent": WORKFLOW_AGENT,
        "input": plan_result.output,
        "output": {
            "framework_summary": "what framework changes were made and why",
            "test_results": "results from running the existing test suite after refactoring",
            "framework_ready": "whether the framework is ready for feature-specific test updates"
        },
        "prompt": (
            "Refactor the framework if necessary, then run the tests and confirm "
            "they all pass before proceeding."
        )
    }
    framework_result = _execute_required_step(framework_step)

    testing_step = {
        "agent": WORKFLOW_AGENT,
        "input": {
            "plan": plan_result.output,
            "framework": framework_result.output
        },
        "output": {
            "updated_tests": "the new or updated tests needed for the feature",
            "test_expectations": "what each test validates",
            "testing_ready": "whether the tests are ready for implementation work"
        },
        "prompt": (
            "Update the tests using `myteam get skill development/testing` so they "
            "describe the intended feature behavior."
        )
    }
    testing_result = _execute_required_step(testing_step)

    implementation_state = {
        "plan": plan_result.output,
        "framework": framework_result.output,
        "tests": testing_result.output,
        "attempt": 0,
        "latest_changes": None,
        "latest_review": None
    }

    while True:
        implementation_state["attempt"] += 1

        implement_step = {
            "agent": WORKFLOW_AGENT,
            "input": implementation_state,
            "output": {
                "code_changes": "the code written for this implementation attempt",
                "completed_slices": "which planned slices were completed",
                "remaining_work": "what still needs to be implemented"
            },
            "prompt": "Implement the next feature slice while preserving the updated tests."
        }
        implement_result = _execute_required_step(implement_step)
        implementation_state["latest_changes"] = implement_result.output

        review_step = {
            "agent": WORKFLOW_AGENT,
            "input": {
                "plan": plan_result.output,
                "tests": testing_result.output,
                "implementation": implement_result.output
            },
            "output": {
                "findings": "review findings for the current implementation",
                "ready": "true when the feature is ready to ship, otherwise false",
                "follow_up_work": "specific changes needed before the next implementation attempt"
            },
            "prompt": (
                "Review implementation using `myteam get role "
                "development/feature-pipeline/code-linter`. Return findings and "
                "whether or not it's ready."
            )
        }
        review_result = _execute_required_step(review_step)
        implementation_state["latest_review"] = review_result.output

        if review_result.output["ready"]:
            return {
                "plan": plan_result.output,
                "framework": framework_result.output,
                "tests": testing_result.output,
                "implementation": implement_result.output,
                "review": review_result.output
            }

def main():
    return feature_pipeline()
