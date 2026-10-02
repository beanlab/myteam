from __future__ import annotations

from pathlib import Path

import pytest

from myteam import explain_resources, onboard


def test_onboard_routes_to_explain_and_warns(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rendered = onboard(tmp_path / "ignored-governing-docs")

    captured = capsys.readouterr()
    assert rendered == explain_resources()
    assert captured.out == ""
    assert captured.err == (
        "Warning: 'myteam onboard' is deprecated; use 'myteam explain' instead.\n"
    )
