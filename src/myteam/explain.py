"""Explanation helpers for myteam resources."""
from __future__ import annotations

from pathlib import Path


USING_MYTEAM_SKILL = Path(__file__).parent / "agent_skills" / "using-myteam.md"


def explain_resources() -> str:
    from .skills import load_skill

    return load_skill(str(USING_MYTEAM_SKILL))


__all__ = ["explain_resources"]
