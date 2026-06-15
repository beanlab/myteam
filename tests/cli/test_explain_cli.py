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
    assert "preferred" in text
