"""Command-facing helpers for the nested session prototype."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import sys
import time
from typing import Any

from .mothership import Mothership
from .protocol import ENV_SESSION_ID, ENV_SOCKET, RpcClient


def start(target: str | None = None, *args: str, workflow_input_json: str | None = None) -> str:
    """Start a managed session.

    If no mothership is present, this function creates one and still uses the
    mothership RPC protocol to launch the first session. If a mothership is
    already present, this function acts as the blocking client/shim used inside
    an agent session.
    """

    argv = _build_argv(target, args, workflow_input_json)
    socket_path = os.environ.get(ENV_SOCKET)
    parent_session_id = os.environ.get(ENV_SESSION_ID)

    if socket_path:
        return _start_via_existing_mothership(
            socket_path=socket_path,
            parent_session_id=parent_session_id,
            argv=argv,
            workflow_input_json=workflow_input_json,
        )

    with Mothership() as mothership:
        client = RpcClient(mothership.socket_path)
        response = client.call(
            "start_session",
            argv=argv,
            parent_session_id=None,
            cwd=os.getcwd(),
            input_json=workflow_input_json,
        )
        result = mothership.run_until_complete(response["request_id"])

    if result is None:
        return ""
    return json.dumps(result)


def report_result(result_json: Any | None = None, *, status: str = "ok") -> None:
    """Report the current managed session's result to the mothership."""

    socket_path = os.environ.get(ENV_SOCKET)
    session_id = os.environ.get(ENV_SESSION_ID)
    if not socket_path or not session_id:
        raise RuntimeError("No active myteam mothership session is available.")

    result = _load_result(result_json)
    RpcClient(socket_path).call(
        "report_result",
        session_id=session_id,
        status=status,
        result=result,
    )


def _start_via_existing_mothership(
    *,
    socket_path: str,
    parent_session_id: str | None,
    argv: list[str],
    workflow_input_json: str | None,
) -> str:
    client = RpcClient(socket_path)
    response = client.call(
        "start_session",
        argv=argv,
        parent_session_id=parent_session_id,
        cwd=os.getcwd(),
        input_json=workflow_input_json,
    )
    request_id = response["request_id"]

    while True:
        poll = client.call("poll_result", request_id=request_id)
        if poll.get("ready"):
            status = str(poll.get("status", "ok"))
            rendered = json.dumps({"status": status, "result": poll.get("result")})
            if status == "ok":
                return rendered
            raise RuntimeError(rendered)
        time.sleep(0.25)


def _build_argv(target: str | None, args: tuple[str, ...], workflow_input_json: str | None) -> list[str]:
    if target is None:
        default_command = os.environ.get("MYTEAM_PROTO_DEFAULT_COMMAND") or os.environ.get("SHELL") or "sh"
        return shlex.split(default_command)

    path = Path(target)
    if path.suffix == ".py" and path.exists():
        argv = [sys.executable, str(path)]
        if workflow_input_json is not None:
            argv.extend(["--input", workflow_input_json])
        argv.extend(args)
        return argv

    # Prototype convention: non-file targets are executable names. Extra Fire
    # positional arguments become argv entries.
    return [target, *args]


def _load_result(result_json: Any | None) -> Any:
    if result_json is None:
        if sys.stdin.isatty():
            return None
        text = sys.stdin.read()
    elif isinstance(result_json, str):
        text = result_json
    else:
        return result_json

    if not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text
