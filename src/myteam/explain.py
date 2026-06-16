"""Explanation helpers for myteam resources."""
from __future__ import annotations

from .templates import get_template


def explain_resources() -> str:
    return get_template("explain_resources.md")


__all__ = ["explain_resources"]
