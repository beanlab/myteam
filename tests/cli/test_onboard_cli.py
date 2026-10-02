from __future__ import annotations

from pathlib import Path

def test_onboard_cli_routes_to_explain_and_warns(run_myteam, tmp_path: Path) -> None:
    explained = run_myteam(tmp_path, "explain")
    result = run_myteam(tmp_path, "onboard")

    assert result.exit_code == explained.exit_code == 0
    assert result.stdout == explained.stdout
    assert result.stderr == (
        "Warning: 'myteam onboard' is deprecated; use 'myteam explain' instead.\n"
    )
