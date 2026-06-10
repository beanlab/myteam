"""Command implementations for the myteam CLI."""
from __future__ import annotations

from . import __version__
from .upgrade import packaged_changelog_text

APP_NAME = 'myteam'


def version() -> str:
    return f"{APP_NAME} {__version__}"


def changelog() -> str:
    return packaged_changelog_text().rstrip()
