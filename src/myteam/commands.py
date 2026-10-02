"""Command implementations for the myteam CLI."""
from __future__ import annotations

import sys
from pathlib import Path


APP_NAME = 'myteam'
ONBOARD_DEPRECATION_WARNING = (
    "Warning: 'myteam onboard' is deprecated; use 'myteam explain' instead."
)


def version() -> str:
    from . import __version__

    return f"{APP_NAME} {__version__}"


def changelog() -> str:
    from .upgrade import packaged_changelog_text

    return packaged_changelog_text().rstrip()


def onboard(root: str | Path | None = None) -> str:
    from .explain import explain_resources

    print(ONBOARD_DEPRECATION_WARNING, file=sys.stderr)
    return explain_resources()
