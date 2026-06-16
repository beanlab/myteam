from __future__ import annotations

from pathlib import Path

from myteam import onboard


def test_onboard_cli_matches_public_api_stdout(run_myteam, tmp_path: Path) -> None:
    result = run_myteam(tmp_path, "onboard")

    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout == onboard()
