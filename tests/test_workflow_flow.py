from __future__ import annotations

import json
from pathlib import Path

from myteam.workflow.models import PtyRunResult


def _write_workflow(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _install_success_runner(monkeypatch):
    def fake_run_pty_session(argv, initial_input, on_output, **kwargs):
        del kwargs
        prompt = argv[-1] if initial_input is None else initial_input
        if "Write the draft." in prompt:
            payload = {
                "status": "OBJECTIVE_COMPLETE",
                "content": {"title": "Draft Title"},
            }
        elif "Review the draft." in prompt:
            assert "Draft Title" in prompt
            payload = {
                "status": "OBJECTIVE_COMPLETE",
                "content": {"winner": "Draft Title"},
            }
        else:
            payload = {
                "status": "OBJECTIVE_COMPLETE",
                "content": {"message": "done"},
            }

        chunk = json.dumps(payload).encode("utf-8")
        on_output(chunk)
        return PtyRunResult(exit_code=0, transcript=chunk.decode("utf-8"))

    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)


def test_start_runs_workflow_successfully_with_yaml(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    _install_success_runner(monkeypatch)
    _write_workflow(
        initialized_project / ".myteam" / "demo.yaml",
        "draft:\n"
        "  prompt: Write the draft.\n"
        "  output:\n"
        "    title: Draft title\n"
        "review:\n"
        "  input:\n"
        "    draft: $draft.output\n"
        "  prompt: Review the draft.\n"
        "  output:\n"
        "    winner: Winning draft\n",
    )

    result = run_myteam_inprocess(initialized_project, "start", "demo")

    assert result.exit_code == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_start_supports_yml_extension(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    _install_success_runner(monkeypatch)
    _write_workflow(
        initialized_project / ".myteam" / "demo.yml",
        "draft:\n"
        "  prompt: Write the draft.\n"
        "  output:\n"
        "    title: Draft title\n",
    )

    result = run_myteam_inprocess(initialized_project, "start", "demo")

    assert result.exit_code == 0
    assert result.stderr == ""


def test_start_supports_prefix_lookup(run_myteam_inprocess, tmp_path: Path, monkeypatch):
    _install_success_runner(monkeypatch)
    _write_workflow(
        tmp_path / "agents" / "demo.yaml",
        "draft:\n"
        "  prompt: Write the draft.\n"
        "  output:\n"
        "    title: Draft title\n",
    )

    result = run_myteam_inprocess(tmp_path, "start", "demo", "--prefix", "agents")

    assert result.exit_code == 0
    assert result.stderr == ""


def test_start_fails_for_missing_workflow(run_myteam_inprocess, initialized_project: Path):
    result = run_myteam_inprocess(initialized_project, "start", "missing")

    assert result.exit_code == 1
    assert "Workflow 'missing' not found" in result.stderr


def test_start_fails_for_malformed_workflow(run_myteam_inprocess, initialized_project: Path):
    _write_workflow(
        initialized_project / ".myteam" / "broken.yaml",
        "draft:\n"
        "  prompt: Write the draft.\n"
        "  output:\n"
        "    - nope\n",
    )

    result = run_myteam_inprocess(initialized_project, "start", "broken")

    assert result.exit_code == 1
    assert "Failed to load workflow 'broken'" in result.stderr


def test_start_stops_after_first_failed_step(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    seen_prompts: list[str] = []

    def fake_run_pty_session(argv, initial_input, on_output, **kwargs):
        del kwargs
        prompt = argv[-1] if initial_input is None else initial_input
        seen_prompts.append(prompt)
        if "Write the draft." in prompt:
            payload = {
                "status": "OBJECTIVE_COMPLETE",
                "content": {"title": "Draft Title"},
            }
            chunk = json.dumps(payload).encode("utf-8")
            on_output(chunk)
            return PtyRunResult(exit_code=0, transcript=chunk.decode("utf-8"))

        return PtyRunResult(exit_code=0, transcript="no completion\n")

    monkeypatch.setattr("myteam.workflow.step_executor.run_pty_session", fake_run_pty_session)

    _write_workflow(
        initialized_project / ".myteam" / "demo.yaml",
        "draft:\n"
        "  prompt: Write the draft.\n"
        "  output:\n"
        "    title: Draft title\n"
        "review:\n"
        "  prompt: Review the draft.\n"
        "  output:\n"
        "    winner: Winning draft\n"
        "publish:\n"
        "  prompt: Publish the draft.\n"
        "  output:\n"
        "    published: yes\n",
    )

    result = run_myteam_inprocess(initialized_project, "start", "demo")

    assert result.exit_code == 1
    assert len(seen_prompts) == 2
    assert any("Write the draft." in prompt for prompt in seen_prompts)
    assert any("Review the draft." in prompt for prompt in seen_prompts)
    assert all("Publish the draft." not in prompt for prompt in seen_prompts)
    assert "Workflow failed at step 'review'" in result.stderr
