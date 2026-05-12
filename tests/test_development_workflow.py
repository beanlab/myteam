from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
DEVELOPMENT_WORKFLOW = ROOT / ".myteam" / "development-workflow" / "development.py"


def load_development_workflow():
    spec = importlib.util.spec_from_file_location(
        "project_development_workflow",
        DEVELOPMENT_WORKFLOW,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_waiting_for_review_status_option_matches_github_project():
    workflow = load_development_workflow()

    assert workflow.STATUS_OPTIONS["Waiting for Review"] == "f576f05d"


def test_complete_step_sets_waiting_for_review_status(monkeypatch):
    workflow = load_development_workflow()
    seen: dict[str, object] = {}

    def fake_set_project_status(state, status):
        seen["status_state"] = state
        seen["status"] = status

    def fake_run_step(*, input, prompt, output):
        seen["input"] = input
        seen["prompt"] = prompt
        return {
            "issue_number": input["issue_number"],
            "issue_id": input["issue_id"],
            "project_item_id": input["project_item_id"],
            "pr_url": "https://github.com/beanlab/myteam/pull/1",
            "completion_summary": "Ready for human review.",
        }

    monkeypatch.setattr(workflow, "set_project_status", fake_set_project_status)
    monkeypatch.setattr(workflow, "run_step", fake_run_step)

    state = {
        "issue_number": 64,
        "issue_id": "I_123",
        "project_item_id": "PVTI_123",
    }

    result = workflow.complete_step(state)

    assert seen["status_state"]["pr_url"] == "https://github.com/beanlab/myteam/pull/1"
    assert seen["status"] == "Waiting for Review"
    assert seen["prompt"] == "Your role is 'development-workflow/complete'."
    assert result["completion_summary"] == "Ready for human review."


def test_artifact_step_resumes_conversation_session(monkeypatch):
    workflow = load_development_workflow()
    seen: dict[str, object] = {}

    def fake_run_step(*, input, prompt, output, session_id=None):
        seen["prompt"] = prompt
        seen["session_id"] = session_id
        return {
            "issue_number": input["issue_number"],
            "issue_id": input["issue_id"],
            "project_item_id": input["project_item_id"],
            "design_summary": "Design recorded.",
            "next_step": "scenario_conversation",
        }

    monkeypatch.setattr(workflow, "run_step", fake_run_step)

    workflow.high_level_design_artifact_step(
        {
            "issue_number": 76,
            "issue_id": "I_123",
            "project_item_id": "PVTI_123",
            "session_id": "thread-123",
        }
    )

    assert seen["prompt"] == "Your role is 'development-workflow/high-level-design-artifact'."
    assert seen["session_id"] == "thread-123"


def test_planning_happy_path_reaches_implementation_with_session_handoff(monkeypatch):
    workflow = load_development_workflow()
    calls: list[dict[str, object]] = []
    statuses: list[str] = []

    base_issue = {
        "issue_number": 76,
        "issue_id": "I_123",
        "project_item_id": "PVTI_123",
    }

    responses = {
        "Your role is 'development-workflow/high-level-design-conversation'.": {
            **base_issue,
            "session_id": "high-level-design-session",
            "approved": True,
            "summary": "Design approved.",
            "next_step": "high_level_design_artifact",
        },
        "Your role is 'development-workflow/high-level-design-artifact'.": {
            **base_issue,
            "design_summary": "Design recorded.",
            "next_step": "scenario_conversation",
        },
        "Your role is 'development-workflow/scenario-conversation'.": {
            **base_issue,
            "session_id": "scenario-session",
            "approved": True,
            "summary": "Scenarios approved.",
            "next_step": "scenario_artifact",
        },
        "Your role is 'development-workflow/scenario-artifact'.": {
            **base_issue,
            "scenarios_summary": "Scenarios recorded.",
            "next_step": "implementation_plan_conversation",
        },
        "Your role is 'development-workflow/implementation-plan-conversation'.": {
            **base_issue,
            "session_id": "implementation-plan-session",
            "approved": True,
            "summary": "Implementation plan approved.",
            "next_step": "implementation_plan_artifact",
        },
        "Your role is 'development-workflow/implementation-plan-artifact'.": {
            **base_issue,
            "implementation_summary": "Implementation plan recorded.",
            "next_step": "implement",
        },
        "Your role is 'development-workflow/implement'.": {
            **base_issue,
            "implementation_summary": "Implemented.",
            "test_results": "Tests passed.",
            "next_step": "review",
        },
        "Your role is 'development-workflow/review'.": {
            **base_issue,
            "review_summary": "Ready.",
            "ready": True,
            "next_step": "wrap_up",
        },
    }

    def fake_set_project_status(state, status):
        statuses.append(status)

    def fake_run_step(*, input, prompt, output, session_id=None):
        calls.append(
            {
                "prompt": prompt,
                "session_id": session_id,
            }
        )
        return dict(responses[prompt])

    monkeypatch.setattr(workflow, "set_project_status", fake_set_project_status)
    monkeypatch.setattr(workflow, "run_step", fake_run_step)

    result = workflow.run_looping_steps(
        {
            **base_issue,
            "start_step": "high_level_design_conversation",
        }
    )

    assert [call["prompt"] for call in calls] == list(responses)
    assert [
        call["session_id"]
        for call in calls
        if str(call["prompt"]).endswith("-artifact'.")
    ] == [
        "high-level-design-session",
        "scenario-session",
        "implementation-plan-session",
    ]
    assert statuses == ["Ready", "In progress"]
    assert result["implementation_summary"] == "Implemented."
    assert result["review_summary"] == "Ready."


def test_conversation_cannot_advance_without_approval():
    workflow = load_development_workflow()

    with pytest.raises(RuntimeError, match="without approval"):
        workflow.validate_next_step(
            "scenario_conversation",
            "scenario_artifact",
            {"approved": False},
        )


def test_unsupported_planning_jump_is_rejected():
    workflow = load_development_workflow()

    with pytest.raises(RuntimeError, match="cannot choose next_step"):
        workflow.validate_next_step(
            "high_level_design_artifact",
            "implementation_plan_conversation",
            {},
        )


def test_old_start_step_aliases_are_supported():
    workflow = load_development_workflow()

    workflow.validate_start_step("scenarios")
    workflow.validate_start_step("design")
    assert workflow.normalize_step_name("scenarios") == "scenario_conversation"
    assert workflow.normalize_step_name("design") == "implementation_plan_conversation"
