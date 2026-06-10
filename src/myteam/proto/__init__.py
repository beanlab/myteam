"""Prototype nested TTY session supervisor.

This package is intentionally small and experimental. It demonstrates the
mothership/client-shim model described in the session logistics docs.
"""
from __future__ import annotations

from .commands import report_result, start

__all__ = ["start", "report_result"]
