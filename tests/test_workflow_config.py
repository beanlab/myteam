from __future__ import annotations

from pathlib import Path

import pytest

from myteam.workflow.config import load_project_workflow_defaults
from myteam.workflow.models import ProjectWorkflowDefaults


def test_load_project_workflow_defaults_returns_none_when_missing(tmp_path: Path):
    (tmp_path / ".myteam").mkdir()

    assert load_project_workflow_defaults(tmp_path) is None


def test_load_project_workflow_defaults_parses_valid_yaml(tmp_path: Path):
    config_dir = tmp_path / ".myteam"
    config_dir.mkdir()
    (config_dir / ".config.yaml").write_text(
        "agent: codex\n"
        "model: gpt-5.4\n"
        "interactive: false\n"
        "session_id: thread-123\n"
        "fork: true\n"
        "extra_args:\n"
        "  - --exec\n"
        "  - pytest -q\n",
        encoding="utf-8",
    )

    defaults = load_project_workflow_defaults(tmp_path)

    assert defaults == ProjectWorkflowDefaults(
        agent="codex",
        model="gpt-5.4",
        interactive=False,
        session_id="thread-123",
        fork=True,
        extra_args=("--exec", "pytest -q"),
    )


def test_load_project_workflow_defaults_rejects_malformed_yaml(tmp_path: Path):
    config_dir = tmp_path / ".myteam"
    config_dir.mkdir()
    (config_dir / ".config.yaml").write_text("agent: [unterminated\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Failed to parse workflow project config"):
        load_project_workflow_defaults(tmp_path)
