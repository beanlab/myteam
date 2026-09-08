from __future__ import annotations

from pathlib import Path


def test_explain_describes_resource_model_and_commands(run_myteam, tmp_path: Path) -> None:
    result = run_myteam(tmp_path, "explain")

    assert result.exit_code == 0
    text = result.stdout.lower()
    assert "skill" in text
    assert "workflow" in text
    assert "hierarch" in text
    assert "myteam list" in text
    assert "myteam load" in text
    assert "myteam start" in text
    assert "myteam where" in text
    assert "preferred" in text
    assert "markdown" in text
    assert "single json object" in text
    assert "listed input" in text
    assert "listed" in text and "output" in text
    assert "python" in text
    assert "arbitrary" in text
    assert "usage" in text
    for option in (
        "--agent",
        "--session-name",
        "--session_name",
        "--model",
        "--reasoning",
        "--interactive",
        "--extra-args",
        "--extra_args",
        "--session-id",
        "--session_id",
        "--fork",
        "--input",
        "--help",
    ):
        assert option in result.stdout
    assert "yaml" in text
    assert "null" in text
    assert "frontmatter" in text
    assert "default" in text
    assert "last" in text
    assert "myteam start" in text and "--model" in text
