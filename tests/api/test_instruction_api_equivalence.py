from __future__ import annotations

from pathlib import Path

from myteam import explain_resources, list_resources, load_skill


def test_explain_api_matches_cli_stdout(run_myteam, tmp_path: Path) -> None:
    result = run_myteam(tmp_path, "explain")

    assert result.exit_code == 0
    assert result.stdout == explain_resources()


def test_list_api_matches_cli_stdout(run_myteam, tmp_path: Path, monkeypatch) -> None:
    resources = tmp_path / "agents"
    resources.mkdir()
    (resources / "skill.md").write_text(
        "---\n"
        "type: skill\n"
        "description: use this skill for API equivalence\n"
        "---\n"
        "Skill body\n",
        encoding="utf-8",
    )
    (resources / "workflow.py").write_text(
        '"""\n'
        'type: workflow\n'
        'description: use this workflow for API equivalence\n'
        '"""\n'
        "raise RuntimeError('must not execute while listing')\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = run_myteam(tmp_path, "list", "agents")

    assert result.exit_code == 0
    assert result.stdout == list_resources("agents")


def test_load_api_matches_cli_stdout(run_myteam, tmp_path: Path) -> None:
    skill = tmp_path / "skill.md"
    skill.write_text(
        "---\n"
        "type: skill\n"
        "description: load through CLI and API\n"
        "---\n"
        "Skill content.\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "load", "skill.md")

    assert result.exit_code == 0
    assert result.stdout == load_skill(str(skill))
