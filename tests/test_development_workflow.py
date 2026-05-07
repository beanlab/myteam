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


def test_next_step_allows_repeat_and_one_step_forward_only():
    workflow = load_development_workflow()

    assert workflow.allowed_next_steps("scenarios") == ("scenarios", "design")
    assert workflow.allowed_next_steps("design") == (
        "scenarios",
        "design",
        "implement",
    )
    assert workflow.allowed_next_steps("implement") == (
        "scenarios",
        "design",
        "implement",
        "review",
    )
    assert workflow.allowed_next_steps("review") == (
        "scenarios",
        "design",
        "implement",
        "review",
        "wrap_up",
    )


def test_next_step_rejects_skip_forward_and_backlog_return():
    workflow = load_development_workflow()

    with pytest.raises(RuntimeError, match="cannot choose next_step 'review'"):
        workflow.validate_next_step("design", "review")

    with pytest.raises(RuntimeError, match="cannot choose next_step 'backlog'"):
        workflow.validate_next_step("review", "backlog")


def test_ensure_issue_sections_adds_missing_workflow_sections():
    workflow = load_development_workflow()

    body = "Created on: 2026-05-07\n\n## Details\n\nExisting detail.\n"

    updated = workflow.ensure_issue_sections(body)

    assert "## Details\n\nExisting detail." in updated
    for section in workflow.ISSUE_SECTIONS:
        assert f"## {section}" in updated
    assert updated.endswith("\n")


def test_ensure_issue_sections_does_not_duplicate_existing_sections():
    workflow = load_development_workflow()

    body = "\n\n".join(f"## {section}\n\nExisting." for section in workflow.ISSUE_SECTIONS)

    updated = workflow.ensure_issue_sections(body)

    assert updated.count("## Scenarios") == 1
    assert updated.count("## Pull Request") == 1


def test_merge_issue_state_preserves_identifiers_and_adds_step_output():
    workflow = load_development_workflow()

    state = {
        "issue_number": 64,
        "issue_id": "I_123",
        "project_item_id": "PVTI_123",
        "backlog_summary": "Backlog item",
    }
    result = {
        "issue_number": 64,
        "issue_id": "I_123",
        "project_item_id": "PVTI_123",
        "next_step": "design",
        "scenarios_summary": "Scenarios written",
    }

    merged = workflow.merge_issue_state(state, result)

    assert merged["issue_number"] == 64
    assert merged["issue_id"] == "I_123"
    assert merged["project_item_id"] == "PVTI_123"
    assert merged["backlog_summary"] == "Backlog item"
    assert merged["scenarios_summary"] == "Scenarios written"


def test_run_looping_steps_follows_returned_next_steps(monkeypatch):
    workflow = load_development_workflow()
    calls: list[str] = []

    def fake_step(name: str, next_step: str):
        def run(state):
            calls.append(name)
            return {
                "issue_number": state["issue_number"],
                "issue_id": state["issue_id"],
                "project_item_id": state["project_item_id"],
                f"{name}_summary": "done",
                "next_step": next_step,
            }

        return run

    monkeypatch.setattr(workflow, "scenarios_step", fake_step("scenarios", "design"))
    monkeypatch.setattr(workflow, "design_step", fake_step("design", "implement"))
    monkeypatch.setattr(workflow, "implement_step", fake_step("implement", "review"))
    monkeypatch.setattr(workflow, "review_step", fake_step("review", "wrap_up"))

    result = workflow.run_looping_steps(
        {
            "issue_number": 64,
            "issue_id": "I_123",
            "project_item_id": "PVTI_123",
        }
    )

    assert calls == ["scenarios", "design", "implement", "review"]
    assert result["issue_number"] == 64
    assert result["review_summary"] == "done"


def test_set_project_status_builds_project_item_edit_command(monkeypatch):
    workflow = load_development_workflow()
    seen: dict[str, object] = {}

    def fake_run(args, *, check):
        seen["args"] = args
        seen["check"] = check

    monkeypatch.setattr(workflow.subprocess, "run", fake_run)

    workflow.set_project_status({"project_item_id": "PVTI_123"}, "Ready")

    assert seen["check"] is True
    assert seen["args"] == [
        "gh",
        "project",
        "item-edit",
        "--id",
        "PVTI_123",
        "--project-id",
        workflow.PROJECT_ID,
        "--field-id",
        workflow.STATUS_FIELD_ID,
        "--single-select-option-id",
        workflow.STATUS_OPTIONS["Ready"],
    ]


def test_set_project_status_requires_project_item_id():
    workflow = load_development_workflow()

    with pytest.raises(RuntimeError, match="without project_item_id"):
        workflow.set_project_status({}, "Ready")
