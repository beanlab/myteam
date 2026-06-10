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
from .protocol import (
    ENV_REQUEST_ID,
    ENV_SESSION_ID,
    ENV_SOCKET,
    KIND_ACK_RESULT,
    KIND_POLL_RESULT,
    KIND_REPORT_RESULT,
    KIND_START_AGENT_SESSION,
    KIND_START_WORKFLOW,
    RpcClient,
)
from ..workflows.results import SessionResult, UsageInfo


def start(target: str | None = None, *args: str, workflow_input_json: str | None = None) -> str:
    """Start a workflow invocation.

    If no mothership is present, this function creates the workflow-level
    supervisor and runs the target workflow under that supervisor. If a
    mothership is already present, this function acts as the blocking
    client/shim used inside a managed agent session.
    """

    argv = _build_workflow_argv(target, args, workflow_input_json)
    socket_path = os.environ.get(ENV_SOCKET)
    parent_session_id = os.environ.get(ENV_SESSION_ID)

    if socket_path:
        return _start_workflow_via_existing_mothership(
            socket_path=socket_path,
            parent_session_id=parent_session_id,
            argv=argv,
            workflow_input_json=workflow_input_json,
        )

    with Mothership() as mothership:
        request_id = mothership.start_top_level_workflow(
            argv=argv,
            cwd=os.getcwd(),
            input_json=workflow_input_json,
        )
        result = mothership.run_until_complete(request_id)

    if result is None:
        return ""
    return json.dumps(result)


def run_agent(
    *,
    prompt: str,
    input: dict[str, Any] | None = None,
    output: dict[str, Any] | None = None,
    agent: str | None = None,
    model: str | None = None,
    reasoning: str | None = None,
    extra_args: tuple[str, ...] | None = None,
    interactive: bool | None = None,
    session_id: str | None = None,
    fork: bool | None = None,
) -> SessionResult:
    """Start an agent session through the active mothership supervisor.

    Prototype policy: plain `run_agent(...)` requires an active supervisor.
    Workflow scripts should be invoked through `myteam start` so the supervisor
    exists for the duration of the workflow invocation.
    """

    socket_path = os.environ.get(ENV_SOCKET)
    if not socket_path:
        raise RuntimeError("run_agent requires an active myteam supervisor. Invoke the workflow with `myteam start`.")

    argv = _build_agent_argv(agent=agent, extra_args=extra_args)
    client = RpcClient(socket_path)
    response = client.call(
        KIND_START_AGENT_SESSION,
        argv=argv,
        prompt=prompt,
        input=input,
        output=output,
        agent=agent,
        model=model,
        reasoning=reasoning,
        interactive=interactive,
        session_id=session_id,
        fork=fork,
        cwd=os.getcwd(),
        parent_session_id=os.environ.get(ENV_SESSION_ID),
    )
    request_id = response["request_id"]
    result = _poll_until_ready(client, request_id)
    client.call(KIND_ACK_RESULT, request_id=request_id)

    if result.get("status") != "ok":
        raise RuntimeError(json.dumps(result))

    payload = result.get("result")
    if not isinstance(payload, dict):
        payload = {"output": {}, "usage": [], "transcript": "", "session_id": None}

    usage = [UsageInfo(**item) for item in payload.get("usage", []) if isinstance(item, dict)]
    output_value = payload.get("output", {})
    if not isinstance(output_value, dict):
        output_value = {"value": output_value}
    return SessionResult(
        output=output_value,
        usage=usage,
        transcript=str(payload.get("transcript") or ""),
        session_id=payload.get("session_id"),
    )


def report_result(result_json: Any | None = None, *, status: str = "ok") -> None:
    """Report the current managed agent session's result to the mothership."""

    socket_path = os.environ.get(ENV_SOCKET)
    session_id = os.environ.get(ENV_SESSION_ID)
    request_id = os.environ.get(ENV_REQUEST_ID)
    if not socket_path or not session_id or not request_id:
        raise RuntimeError("No active myteam mothership session is available.")

    result = _load_result(result_json)
    RpcClient(socket_path).call(
        KIND_REPORT_RESULT,
        request_id=request_id,
        session_id=session_id,
        status=status,
        output=result,
    )


def _start_workflow_via_existing_mothership(
    *,
    socket_path: str,
    parent_session_id: str | None,
    argv: list[str],
    workflow_input_json: str | None,
) -> str:
    client = RpcClient(socket_path)
    response = client.call(
        KIND_START_WORKFLOW,
        argv=argv,
        parent_session_id=parent_session_id,
        cwd=os.getcwd(),
        input_json=workflow_input_json,
    )
    request_id = response["request_id"]
    result = _poll_until_ready(client, request_id)
    client.call(KIND_ACK_RESULT, request_id=request_id)

    status = str(result.get("status", "ok"))
    rendered = json.dumps({"status": status, "result": result.get("result")})
    if status == "ok":
        return rendered
    raise RuntimeError(rendered)


def _poll_until_ready(client: RpcClient, request_id: str) -> dict[str, Any]:
    while True:
        poll = client.call(KIND_POLL_RESULT, request_id=request_id)
        if poll.get("ready"):
            return poll
        time.sleep(0.25)


def _build_workflow_argv(target: str | None, args: tuple[str, ...], workflow_input_json: str | None) -> list[str]:
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


def _build_agent_argv(*, agent: str | None, extra_args: tuple[str, ...] | None) -> list[str]:
    if agent:
        return [agent, *(extra_args or ())]
    default_command = os.environ.get("MYTEAM_PROTO_DEFAULT_AGENT_COMMAND") or os.environ.get("MYTEAM_PROTO_DEFAULT_COMMAND")
    if default_command:
        argv = shlex.split(default_command)
        argv.extend(extra_args or ())
        return argv
    raise RuntimeError("No agent command configured. Provide `agent=` or set MYTEAM_PROTO_DEFAULT_AGENT_COMMAND.")


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
