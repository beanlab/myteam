"""Prototype nested TTY session supervisor.

This package is intentionally small and experimental. It demonstrates the
workflow-level mothership/client-shim model described in the session docs.
"""
from __future__ import annotations

from .commands import report_result, run_agent, start

__all__ = ["start", "run_agent", "report_result"]
