from __future__ import annotations

import importlib.util
from pathlib import Path


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
