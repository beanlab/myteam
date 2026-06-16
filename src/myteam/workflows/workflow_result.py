"""Explicit workflow result reporting for managed workflows."""
from __future__ import annotations

import os

from .execution.protocol import ENV_SOCKET, ENV_WORKFLOW_INVOCATION_ID, KIND_WORKFLOW_RESULT, RpcClient


def report_workflow_result(text: str | None = None, end='\n') -> None:
    """Append caller-facing result text for the current managed workflow.

    Ordinary workflow stdout/stderr are live display/logging streams. This
    function reports the text that `myteam start` should return to its caller
    after the workflow exits. Passing ``None`` appends no text.
    """

    if text is not None and not isinstance(text, str):
        raise TypeError("workflow result text must be a string or None.")

    text += end
    
    socket_path = os.environ.get(ENV_SOCKET)
    request_id = os.environ.get(ENV_WORKFLOW_INVOCATION_ID)
    if not socket_path or not request_id:
        raise RuntimeError("No active myteam workflow is available.")

    RpcClient(socket_path).call(KIND_WORKFLOW_RESULT, request_id=request_id, text=text)
