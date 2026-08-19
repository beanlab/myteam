"""
type: workflow
description: Develop a feature from discovery through implementation, review, documentation, and release.
usage: no arguments; the interactive discovery session will ask for the feature request
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

from myteam import SessionResult, report_workflow_result, run_agent

PROMPT_DIRECTORY = Path(__file__).parent
AGENT = "pi"
STRONG_MODEL = "openai/gpt-5.6-sol"
MID_MODEL = "openai/gpt-5.6-terra"
ECONOMICAL_MODEL = "openai/gpt-5.6-luna"


@dataclass(frozen=True)
class SessionSettings:
    model: str
    reasoning: str


SESSION_SETTINGS = {
    "product": SessionSettings(model=STRONG_MODEL, reasoning="high"),
    "design": SessionSettings(model=STRONG_MODEL, reasoning="high"),
    "planning": SessionSettings(model=STRONG_MODEL, reasoning="high"),
    "plan_review": SessionSettings(model=STRONG_MODEL, reasoning="high"),
    "delivery": SessionSettings(model=STRONG_MODEL, reasoning="high"),
    "code_review": SessionSettings(model=STRONG_MODEL, reasoning="high"),
    "documentation": SessionSettings(model=MID_MODEL, reasoning="medium"),
    "release": SessionSettings(model=ECONOMICAL_MODEL, reasoning="low"),
}
STEP_SESSIONS = {
    "01-discover.md.jinja": "product",
    "02-evaluate.md.jinja": "design",
    "03-select-approach.md.jinja": "design",
    "04-plan.md.jinja": "planning",
    "05-review-plan.md.jinja": "plan_review",
    "06-write-tests.md.jinja": "delivery",
    "07-implement.md.jinja": "delivery",
    "08-remediate.md.jinja": "delivery",
    "08-review-code.md.jinja": "code_review",
    "08-resolve-review.md.jinja": "code_review",
    "09-document.md.jinja": "documentation",
    "10-sign-off.md.jinja": "product",
    "11-wrap-up.md.jinja": "release",
}
STEP_CONTEXTS = {
    "01-discover.md.jinja": ("product",),
    "02-evaluate.md.jinja": ("architecture",),
    "03-select-approach.md.jinja": ("architecture",),
    "04-plan.md.jinja": ("architecture", "testing", "documentation"),
    "05-review-plan.md.jinja": ("architecture", "testing"),
    "06-write-tests.md.jinja": ("testing",),
    "07-implement.md.jinja": ("implementation", "testing"),
    "08-review-code.md.jinja": ("implementation", "testing", "security"),
    "08-remediate.md.jinja": ("implementation", "testing"),
    "08-resolve-review.md.jinja": ("implementation", "testing", "security"),
    "09-document.md.jinja": ("documentation",),
    "10-sign-off.md.jinja": ("product",),
    "11-wrap-up.md.jinja": ("release",),
}

FEATURE_BRIEF = {
    "motivation": "Why the feature is wanted.",
    "desired_behavior": "The requested behavior.",
    "acceptance_criteria": "Observable criteria that define completion.",
    "non_goals": "Related work that is explicitly out of scope.",
    "affected_contracts": "Public APIs or behaviors that may change.",
    "edge_cases": "Important boundary and failure cases.",
    "unresolved_questions": "Questions that remain unanswered; empty when discovery is complete.",
}
SOLUTION_ANALYSIS = {
    "viable_approaches": "Implementation approaches and their tradeoffs.",
    "recommendation": "Recommended approach and rationale.",
    "required_refactoring": "Refactoring needed before or during implementation.",
    "compatibility_and_migration": "Compatibility and migration consequences.",
    "risks": "Security, correctness, reliability, performance, and usability risks.",
    "rejected_alternatives": "Alternatives rejected before human review and why.",
    "decisions_needed": "Decisions the user must make.",
}
DESIGN_DECISION = {
    "selected_approach": "The approach selected with the user.",
    "rationale": "Why it was selected.",
    "accepted_tradeoffs": "Tradeoffs explicitly accepted by the user.",
    "required_refactoring": "Refactoring included in the selected approach.",
    "compatibility_policy": "How compatibility and migration will be handled.",
    "unresolved_items": "Remaining non-blocking items; blocking items must be resolved first.",
    "approved_by_user": "Boolean confirming the user's approval.",
}
EXECUTION_PLAN = {
    "baseline_checks": "Checks to establish the repository baseline.",
    "implementation_changes": "Ordered code changes.",
    "test_changes": "Tests to add or change and the contracts they protect.",
    "refactoring_sequence": "Ordered prerequisite and feature-related refactoring.",
    "documentation_changes": "Documentation that must be updated.",
    "files_expected_to_change": "Expected files, classes, and functions affected.",
    "validation_commands": "Commands used to verify the completed work.",
    "risks_and_safeguards": "Implementation risks and their safeguards.",
}
PLAN_REVIEW = {
    "verdict": "One of: approved, revise.",
    "return_to": "When revision is required, one of: discovery, design, planning; empty when approved.",
    "correctness_findings": "Correctness problems in the plan.",
    "missing_work": "Necessary work omitted from the plan.",
    "unnecessary_complexity": "Complexity that should be removed.",
    "test_coverage_gaps": "Public contracts or risky behavior not adequately tested.",
    "required_revisions": "Specific revisions required before approval.",
}
TEST_STATE = {
    "baseline_result": "Tests run before modification and their result.",
    "tests_changed": "Tests added or changed.",
    "expected_failures": "Failures demonstrating the missing feature behavior.",
    "unexpected_failures": "Any failures that were not expected.",
    "ready_for_implementation": "Boolean indicating whether implementation may begin.",
}
IMPLEMENTATION_RESULT = {
    "changes_made": "Code and test changes made.",
    "deviations_from_plan": "Any deviations and their rationale.",
    "refactoring_performed": "Refactoring performed.",
    "tests_run": "Tests and validation commands run.",
    "test_results": "Results of validation.",
    "remaining_concerns": "Known concerns that remain.",
}
CODE_REVIEW = {
    "verdict": "One of: approved, changes_required.",
    "return_to": "When changes are required, one of: discovery, design, planning, implementation; empty when approved.",
    "correctness_findings": "Correctness defects.",
    "security_findings": "Security or data-integrity defects.",
    "maintainability_findings": "Maintainability and design concerns.",
    "unnecessary_complexity": "Complexity or scope that should be removed.",
    "contract_or_test_gaps": "Missing contract coverage or inadequate tests.",
    "required_changes": "Specific changes required before approval.",
}
REMEDIATION_RESULT = {
    "implementation_result": IMPLEMENTATION_RESULT,
    "findings_addressed": "Review findings addressed and how.",
    "findings_not_addressed": "Findings not applied and the justification for each.",
    "review_disputed": "Boolean indicating whether any required review finding is disputed.",
    "tests_changed": "Tests added or adjusted while addressing the findings.",
    "ready_for_re_review": "Boolean indicating whether re-review may begin.",
}
REVIEW_RESOLUTION = {
    "decision": "One of: remediate, re_review, discovery, design, planning, stop.",
    "rationale": "The user's reason for the decision.",
    "binding_direction": "Direction the reviewer and delivery agent must follow.",
    "resolved_by_user": "Boolean confirming the user made the decision.",
}
DOCUMENTATION_RESULT = {
    "files_changed": "Documentation files changed.",
    "user_facing_updates": "User-facing documentation updates.",
    "agent_facing_updates": "Agent-facing documentation updates.",
    "validation_performed": "Documentation and final project validation performed.",
    "intentionally_unchanged_docs": "Relevant documentation intentionally left unchanged and why.",
}
ACCEPTANCE = {
    "criteria_status": "Status of every acceptance criterion.",
    "deviations": "Any deviation from the agreed feature.",
    "decision": "One of: approved, changes_requested.",
    "return_to": "When changes are requested, one of: discovery, planning, documentation.",
    "requested_changes": "Changes requested by the user; empty when approved.",
}
WRAP_UP = {
    "version_change": "Version action performed or skipped.",
    "changelog_change": "Changelog action performed or skipped.",
    "commit": "Commit action performed or skipped.",
    "pull_request": "Pull-request action performed or skipped.",
    "actions_skipped": "Actions not authorized by the user.",
    "final_repository_state": "Final repository and validation state.",
}


class WorkflowStopped(Exception):
    """Raised when an agent session ends without its required result."""


class ReturnToStep(Exception):
    """Carries review feedback back to an earlier workflow step."""

    def __init__(self, feedback: dict[str, Any], source: str):
        super().__init__(source)
        self.feedback = feedback
        self.source = source


class ReturnToDiscovery(ReturnToStep):
    """Requests another pass through discovery and every subsequent step."""


class ReturnToDesign(ReturnToStep):
    """Requests another pass through design and every subsequent step."""


class ReturnToPlanning(ReturnToStep):
    """Requests another pass through planning and every subsequent step."""


class ReturnToImplementation(ReturnToStep):
    """Requests implementation remediation followed by another code review."""


class ReturnToDocumentation(ReturnToStep):
    """Requests another documentation pass followed by sign-off."""


@dataclass
class FlowState:
    feature_brief: dict[str, Any] | None = None
    solution_analysis: dict[str, Any] | None = None
    design_decision: dict[str, Any] | None = None
    execution_plan: dict[str, Any] | None = None
    test_state: dict[str, Any] | None = None
    implementation_result: dict[str, Any] | None = None
    remediation_result: dict[str, Any] | None = None
    plan_review: dict[str, Any] | None = None
    code_review: dict[str, Any] | None = None
    review_resolution: dict[str, Any] | None = None
    documentation_result: dict[str, Any] | None = None
    acceptance: dict[str, Any] | None = None
    feedback: dict[str, Any] | None = None
    feedback_source: str | None = None
    discovery_session: SessionResult | None = None
    design_session: SessionResult | None = None
    planner_session: SessionResult | None = None
    plan_reviewer_session: SessionResult | None = None
    delivery_session: SessionResult | None = None
    code_reviewer_session: SessionResult | None = None
    documentation_session: SessionResult | None = None


def run_step(
        prompt_name: str,
        *,
        output: dict[str, Any],
        input: dict[str, Any] | None = None,
        interactive: bool = False,
        session_id: str | None = None,
) -> SessionResult:
    prompt_path = PROMPT_DIRECTORY / prompt_name
    context_tags = STEP_CONTEXTS.get(prompt_name)
    if context_tags is None:
        raise WorkflowStopped(f"No project-context tags configured for {prompt_name}")
    session_name = STEP_SESSIONS.get(prompt_name)
    if session_name is None:
        raise WorkflowStopped(f"No session configured for {prompt_name}")
    settings = SESSION_SETTINGS[session_name]
    step_input = {
        **(input or {}),
        "workflow_step": prompt_name.removesuffix(".md.jinja"),
        "context_tags": context_tags,
    }
    result = run_agent(
        prompt=prompt_path.read_text(),
        prompt_source_path=prompt_path,
        input=step_input,
        output=output,
        agent=AGENT,
        model=settings.model,
        reasoning=settings.reasoning,
        interactive=interactive,
        session_id=session_id,
    )
    if result.output is None:
        raise WorkflowStopped(f"{prompt_name} ended without reporting a result")
    return result


def require_value(result: SessionResult, field: str, allowed: set[str]) -> str:
    value = result.output.get(field) if result.output is not None else None
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise WorkflowStopped(f"Expected {field} to be one of {choices}; received {value!r}")
    return str(value)


def session_id(session: SessionResult | None) -> str | None:
    return session.session_id if session is not None else None


def set_feedback(state: FlowState, signal: ReturnToStep):
    state.feedback = signal.feedback
    state.feedback_source = signal.source


def clear_feedback(state: FlowState):
    state.feedback = None
    state.feedback_source = None


def return_to_step(
        return_to: str,
        feedback: dict[str, Any],
        source: str,
) -> NoReturn:
    routes = {
        "discovery": ReturnToDiscovery,
        "design": ReturnToDesign,
        "planning": ReturnToPlanning,
        "implementation": ReturnToImplementation,
        "documentation": ReturnToDocumentation,
    }
    raise routes[return_to](feedback, source)


def project_context(state: FlowState) -> dict[str, Any]:
    return {
        "feature_brief": state.feature_brief,
        "design_decision": state.design_decision,
    }


def delivery_context(state: FlowState) -> dict[str, Any]:
    return {**project_context(state), "execution_plan": state.execution_plan}


def run_discovery(state: FlowState) -> dict[str, Any]:
    while True:
        state.discovery_session = run_step(
            "01-discover.md.jinja",
            input={
                "previous_feature_brief": state.feature_brief,
                "feedback": state.feedback,
                "feedback_source": state.feedback_source,
            },
            output=FEATURE_BRIEF,
            interactive=True,
            session_id=session_id(state.discovery_session),
        )
        state.feature_brief = state.discovery_session.output
        clear_feedback(state)

        try:
            return run_design(state)
        except ReturnToDiscovery as signal:
            set_feedback(state, signal)


def run_design(state: FlowState) -> dict[str, Any]:
    while True:
        state.design_session = run_step(
            "02-evaluate.md.jinja",
            input={
                "feature_brief": state.feature_brief,
                "previous_solution_analysis": state.solution_analysis,
                "previous_design_decision": state.design_decision,
                "feedback": state.feedback,
                "feedback_source": state.feedback_source,
            },
            output=SOLUTION_ANALYSIS,
            session_id=session_id(state.design_session),
        )
        state.solution_analysis = state.design_session.output

        state.design_session = run_step(
            "03-select-approach.md.jinja",
            input={
                "feature_brief": state.feature_brief,
                "solution_analysis": state.solution_analysis,
                "previous_design_decision": state.design_decision,
            },
            output=DESIGN_DECISION,
            interactive=True,
            session_id=state.design_session.session_id,
        )
        if state.design_session.output.get("approved_by_user") is not True:
            raise WorkflowStopped("The selected design was not approved by the user")
        state.design_decision = state.design_session.output
        clear_feedback(state)

        try:
            return run_planning(state)
        except ReturnToDesign as signal:
            set_feedback(state, signal)


def run_planning(state: FlowState) -> dict[str, Any]:
    while True:
        state.planner_session = run_step(
            "04-plan.md.jinja",
            input={
                **project_context(state),
                "previous_execution_plan": state.execution_plan,
                "previous_implementation_result": state.implementation_result,
                "feedback": state.feedback,
                "feedback_source": state.feedback_source,
            },
            output=EXECUTION_PLAN,
            session_id=session_id(state.planner_session),
        )
        state.execution_plan = state.planner_session.output

        try:
            return run_plan_review(state)
        except ReturnToPlanning as signal:
            set_feedback(state, signal)


def run_plan_review(state: FlowState) -> dict[str, Any]:
    state.plan_reviewer_session = run_step(
        "05-review-plan.md.jinja",
        input={
            **delivery_context(state),
            "previous_plan_review": state.plan_review,
            "feedback": state.feedback,
            "feedback_source": state.feedback_source,
        },
        output=PLAN_REVIEW,
        session_id=session_id(state.plan_reviewer_session),
    )
    state.plan_review = state.plan_reviewer_session.output

    verdict = require_value(state.plan_reviewer_session, "verdict", {"approved", "revise"})
    if verdict == "revise":
        return_to = require_value(
            state.plan_reviewer_session,
            "return_to",
            {"discovery", "design", "planning"},
        )
        return_to_step(return_to, state.plan_review, "plan_review")

    clear_feedback(state)
    return run_tests(state)


def run_tests(state: FlowState) -> dict[str, Any]:
    state.delivery_session = run_step(
        "06-write-tests.md.jinja",
        input={
            **delivery_context(state),
            "previous_test_state": state.test_state,
            "previous_implementation_result": state.implementation_result,
            "feedback": state.feedback,
            "feedback_source": state.feedback_source,
        },
        output=TEST_STATE,
        session_id=session_id(state.delivery_session),
    )
    state.test_state = state.delivery_session.output
    if state.test_state.get("ready_for_implementation") is not True:
        raise WorkflowStopped("The tests are not ready for implementation")

    return run_implementation(state)


def run_initial_implementation(state: FlowState):
    state.delivery_session = run_step(
        "07-implement.md.jinja",
        input={
            **delivery_context(state),
            "previous_implementation_result": state.implementation_result,
            "test_state": state.test_state,
            "feedback": state.feedback,
            "feedback_source": state.feedback_source,
        },
        output=IMPLEMENTATION_RESULT,
        session_id=session_id(state.delivery_session),
    )
    state.implementation_result = state.delivery_session.output
    state.remediation_result = None
    state.review_resolution = None


def run_remediation(state: FlowState, review_feedback: dict[str, Any]):
    state.delivery_session = run_step(
        "08-remediate.md.jinja",
        input={
            **delivery_context(state),
            "implementation_result": state.implementation_result,
            "code_review": review_feedback,
            "review_resolution": state.review_resolution,
        },
        output=REMEDIATION_RESULT,
        session_id=session_id(state.delivery_session),
    )
    state.remediation_result = state.delivery_session.output
    implementation_result = state.remediation_result.get("implementation_result")
    if not isinstance(implementation_result, dict):
        raise WorkflowStopped(
            "Remediation did not report a canonical implementation_result"
        )
    if state.remediation_result.get("ready_for_re_review") is not True:
        raise WorkflowStopped("Remediation is not ready for re-review")
    if not isinstance(state.remediation_result.get("review_disputed"), bool):
        raise WorkflowStopped("Remediation did not report whether the review is disputed")
    state.implementation_result = implementation_result


def run_review_resolution(state: FlowState, reason: str) -> str:
    state.code_reviewer_session = run_step(
        "08-resolve-review.md.jinja",
        input={
            **delivery_context(state),
            "implementation_result": state.implementation_result,
            "code_review": state.code_review,
            "remediation_result": state.remediation_result,
            "previous_review_resolution": state.review_resolution,
            "escalation_reason": reason,
        },
        output=REVIEW_RESOLUTION,
        interactive=True,
        session_id=session_id(state.code_reviewer_session),
    )
    if state.code_reviewer_session.output.get("resolved_by_user") is not True:
        raise WorkflowStopped("The review disagreement was not resolved by the user")
    state.review_resolution = state.code_reviewer_session.output
    decision = require_value(
        state.code_reviewer_session,
        "decision",
        {"remediate", "re_review", "discovery", "design", "planning", "stop"},
    )
    if decision in {"discovery", "design", "planning"}:
        return_to_step(decision, state.review_resolution, "review_resolution")
    if decision == "stop":
        raise WorkflowStopped("The user stopped the workflow during review resolution")
    return decision


def run_implementation(state: FlowState) -> dict[str, Any]:
    run_initial_implementation(state)
    review_feedback: dict[str, Any] | None = None
    remediation_cycles = 0
    authorized_remediation = False

    while True:
        if review_feedback is not None:
            if remediation_cycles >= 2 and not authorized_remediation:
                decision = run_review_resolution(state, "remediation_limit")
                if decision == "re_review":
                    review_feedback = None
                else:
                    authorized_remediation = True

            if review_feedback is not None:
                run_remediation(state, review_feedback)
                remediation_cycles += 1
                authorized_remediation = False
                if state.remediation_result.get("review_disputed") is True:
                    decision = run_review_resolution(state, "finding_disputed")
                    if decision == "remediate":
                        authorized_remediation = True
                        continue
                review_feedback = None

        try:
            return run_code_review(state)
        except ReturnToImplementation as signal:
            review_feedback = signal.feedback


def run_code_review(state: FlowState) -> dict[str, Any]:
    state.code_reviewer_session = run_step(
        "08-review-code.md.jinja",
        input={
            **delivery_context(state),
            "implementation_result": state.implementation_result,
            "remediation_result": state.remediation_result,
            "previous_code_review": state.code_review,
            "review_resolution": state.review_resolution,
        },
        output=CODE_REVIEW,
        session_id=session_id(state.code_reviewer_session),
    )
    state.code_review = state.code_reviewer_session.output

    verdict = require_value(
        state.code_reviewer_session,
        "verdict",
        {"approved", "changes_required"},
    )
    if verdict == "changes_required":
        return_to = require_value(
            state.code_reviewer_session,
            "return_to",
            {"discovery", "design", "planning", "implementation"},
        )
        return_to_step(return_to, state.code_review, "code_review")

    return run_documentation(state)


def run_documentation(state: FlowState) -> dict[str, Any]:
    while True:
        state.documentation_session = run_step(
            "09-document.md.jinja",
            input={
                **delivery_context(state),
                "implementation_result": state.implementation_result,
                "code_review": state.code_review,
                "previous_documentation_result": state.documentation_result,
                "feedback": state.feedback,
                "feedback_source": state.feedback_source,
            },
            output=DOCUMENTATION_RESULT,
            session_id=session_id(state.documentation_session),
        )
        state.documentation_result = state.documentation_session.output

        try:
            return run_sign_off(state)
        except ReturnToDocumentation as signal:
            set_feedback(state, signal)


def run_sign_off(state: FlowState) -> dict[str, Any]:
    state.discovery_session = run_step(
        "10-sign-off.md.jinja",
        input={
            **delivery_context(state),
            "implementation_result": state.implementation_result,
            "code_review": state.code_review,
            "documentation_result": state.documentation_result,
            "previous_acceptance": state.acceptance,
        },
        output=ACCEPTANCE,
        interactive=True,
        session_id=state.discovery_session.session_id,
    )
    state.acceptance = state.discovery_session.output

    decision = require_value(
        state.discovery_session,
        "decision",
        {"approved", "changes_requested"},
    )
    if decision == "changes_requested":
        return_to = require_value(
            state.discovery_session,
            "return_to",
            {"discovery", "planning", "documentation"},
        )
        return_to_step(return_to, state.acceptance, "sign_off")

    clear_feedback(state)
    return run_wrap_up(state)


def run_wrap_up(state: FlowState) -> dict[str, Any]:
    wrap_up = run_step(
        "11-wrap-up.md.jinja",
        input={
            **delivery_context(state),
            "implementation_result": state.implementation_result,
            "code_review": state.code_review,
            "documentation_result": state.documentation_result,
            "acceptance": state.acceptance,
        },
        output=WRAP_UP,
        interactive=True,
    )
    return {
        "status": "complete",
        "feature_brief": state.feature_brief,
        "solution_analysis": state.solution_analysis,
        "design_decision": state.design_decision,
        "execution_plan": state.execution_plan,
        "plan_review": state.plan_review,
        "test_state": state.test_state,
        "implementation_result": state.implementation_result,
        "remediation_result": state.remediation_result,
        "code_review": state.code_review,
        "review_resolution": state.review_resolution,
        "documentation_result": state.documentation_result,
        "acceptance": state.acceptance,
        "wrap_up": wrap_up.output,
    }


def main():
    try:
        report_workflow_result(json.dumps(run_discovery(FlowState()), indent=2))
    except WorkflowStopped as error:
        report_workflow_result(json.dumps({"status": "stopped", "reason": str(error)}, indent=2))


if __name__ == "__main__":
    main()
