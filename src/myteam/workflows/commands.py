from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
import shlex
import sys
import time
from typing import Any, TypedDict

from .. import templates
from ..config import WorkflowDefaults
from ..templates import get_template_file
from .agent_session import build_agent_prompt, run_agent_session
from .execution.mothership import Mothership
from .execution.protocol import (
    ENV_SESSION_ID,
    ENV_SOCKET,
    KIND_ACK_RESULT,
    KIND_POLL_RESULT,
    KIND_START_WORKFLOW,
    RpcClient,
)
from .results import SessionResult, UsageInfo

ENCODING = "utf-8"


class AgentSettings(TypedDict, total=False):
    agent: str | None
    model: str | None
    reasoning: str | None
    interactive: bool | None
    extra_args: tuple[str, ...] | list[str] | None
    session_id: str | None
    fork: bool | None


class MarkdownWorkflowInfo(AgentSettings, total=False):
    input: dict[str, Any] | None
    prompt: str
    output: dict[str, Any] | None


def new_workflow(workflow_name: str, parents: bool = False) -> None:
    """Create a new workflow file from the packaged workflow template."""

    workflow_path = Path(workflow_name)
    if workflow_path.exists():
        print(f"Workflow '{workflow_path}' already exists at {workflow_path}", file=sys.stderr)
        raise SystemExit(1)

    if workflow_path.suffix == "":
        print("Workflow files must end in .md or .py.", file=sys.stderr)
        raise SystemExit(1)

    if not workflow_path.parent.exists():
        if not parents:
            print(f"Path for '{workflow_path}' is not a directory: {workflow_path.parent}", file=sys.stderr)
            raise SystemExit(1)
        workflow_path.parent.mkdir(parents=True)

    suffix = workflow_path.suffix.lower()
    if suffix == ".md":
        workflow_path.write_text(templates.get_template("new_workflow.md"), encoding=ENCODING)
    elif suffix == ".py":
        template_name = "new_workflow.py"
        try:
            content = templates.get_template(template_name)
        except FileNotFoundError:
            content = _default_python_workflow_template()
        workflow_path.write_text(content, encoding=ENCODING)
    else:
        print(f"Workflow '{workflow_name}' has unsupported extension '{workflow_path.suffix}'.", file=sys.stderr)
        raise SystemExit(1)

    print("File", workflow_path.absolute(), "created")


def resolve_agent_settings(
    explicit_settings: dict[str, Any] | None,
    defaults: WorkflowDefaults | dict[str, Any] | None = None,
) -> AgentSettings:
    """Merge frontmatter/explicit agent settings with workflow defaults."""

    explicit_settings = explicit_settings or {}
    result: AgentSettings = {}
    fields = ("agent", "model", "reasoning", "interactive", "extra_args", "session_id", "fork")
    for field in fields:
        value = explicit_settings.get(field)
        if value is None and defaults is not None:
            if isinstance(defaults, dict):
                value = defaults.get(field)
            else:
                value = getattr(defaults, field, None)
        if value is not None:
            if field == "extra_args" and isinstance(value, list):
                value = tuple(str(item) for item in value)
            result[field] = value
    return result


def start_workflow(
    workflow_name: str | None = None,
    *args: str,
    workflow_input_json: str | None = None,
    input: str | None = None,
) -> str:
    """Start a workflow invocation under the workflow supervisor."""

    result = _start_workflow_result(
        workflow_name=workflow_name,
        args=args,
        workflow_input_json=workflow_input_json if workflow_input_json is not None else input,
    )
    if result is None:
        return ""
    return json.dumps({
        "output": result.output,
        "usage": [asdict(item) for item in result.usage],
    })


def start_workflow_cli(
    workflow_name: str | None = None,
    *args: str,
    workflow_input_json: str | None = None,
    input: str | None = None,
) -> None:
    """CLI entrypoint for `myteam start`."""

    result = _start_workflow_result(
        workflow_name=workflow_name,
        args=args,
        workflow_input_json=workflow_input_json if workflow_input_json is not None else input,
    )
    if result is None:
        return
    _print_session_result(result)


def run_agent(
    *,
    prompt: str,
    input: dict[str, Any] | None = None,
    output: dict[str, Any] | None = None,
    agent: str | None = None,
    model: str | None = None,
    reasoning: str | None = None,
    extra_args: tuple[str, ...] | list[str] | None = None,
    interactive: bool | None = None,
    session_id: str | None = None,
    fork: bool | None = None,
) -> SessionResult:
    """Start and manage one child agent session."""

    return run_agent_session(
        prompt=prompt,
        input=input,
        output=output,
        agent=agent,
        model=model,
        reasoning=reasoning,
        extra_args=extra_args,
        interactive=interactive,
        session_id=session_id,
        fork=fork,
    )


def _start_workflow_result(
    *,
    workflow_name: str | None,
    args: tuple[str, ...],
    workflow_input_json: str | None,
) -> SessionResult | None:
    argv = _build_workflow_argv(workflow_name, args, workflow_input_json)
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
        return None

    status = str(result.get("status", "ok")) if isinstance(result, dict) else "ok"
    if status == "ok":
        payload = result.get("result") if isinstance(result, dict) and "result" in result else result
        return _session_result_from_payload(payload)
    raise RuntimeError(
        json.dumps({"status": status, "result": result.get("result") if isinstance(result, dict) else result})
    )


def _start_workflow_via_existing_mothership(
    *,
    socket_path: str,
    parent_session_id: str | None,
    argv: list[str],
    workflow_input_json: str | None,
) -> SessionResult:
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
    if status == "ok":
        return _session_result_from_payload(result.get("result"))
    raise RuntimeError(json.dumps({"status": status, "result": result.get("result")}))


def _poll_until_ready(client: RpcClient, request_id: str) -> dict[str, Any]:
    while True:
        poll = client.call(KIND_POLL_RESULT, request_id=request_id)
        if poll.get("ready"):
            return poll
        time.sleep(0.25)


def _session_result_from_payload(payload: Any) -> SessionResult:
    if payload is None:
        return SessionResult(exit_code=0, output=None, usage=[], transcript="", session_id=None)

    if not isinstance(payload, dict):
        return SessionResult(exit_code=0, output={"value": payload}, usage=[], transcript="", session_id=None)

    if not _is_session_result_payload(payload):
        return SessionResult(exit_code=0, output=payload, usage=[], transcript="", session_id=None)

    usage = [UsageInfo(**item) for item in payload.get("usage", []) if isinstance(item, dict)]
    output_value = payload.get("output")
    if output_value is not None and not isinstance(output_value, dict):
        output_value = {"value": output_value}
    return SessionResult(
        exit_code=_coerce_exit_code(payload.get("exit_code")),
        output=output_value,
        usage=usage,
        transcript=str(payload.get("transcript") or ""),
        session_id=payload.get("session_id"),
    )


def _coerce_exit_code(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    return 0


def _is_session_result_payload(payload: dict[str, Any]) -> bool:
    return "output" in payload and bool({"usage", "transcript", "session_id", "nonce"} & payload.keys())


def _print_session_result(result: SessionResult) -> None:
    print(json.dumps([asdict(item) for item in result.usage], indent=2, sort_keys=True), file=sys.stderr)
    print(json.dumps(result.output), file=sys.stdout)


def _build_workflow_argv(target: str | None, args: tuple[str, ...], workflow_input_json: str | None) -> list[str]:
    if target is None:
        default_command = os.environ.get("MYTEAM_DEFAULT_WORKFLOW_COMMAND") or os.environ.get("SHELL") or "sh"
        return shlex.split(default_command)

    path = Path(target)
    if path.exists():
        suffix = path.suffix.lower()
        absolute = str(path.resolve())
        if suffix == ".py":
            argv = [sys.executable, absolute]
            if workflow_input_json is not None:
                argv.extend(["--input", workflow_input_json])
            argv.extend(args)
            return argv
        if suffix == ".md":
            argv = [
                sys.executable,
                str(get_template_file("workflow_markdown_wrapper.py")),
                absolute,
                workflow_input_json or "{}",
            ]
            argv.extend(args)
            return argv
        raise RuntimeError(f"Workflow '{target}' has unsupported extension '{path.suffix}'.")

    return [target, *args]


def _build_agent_prompt(
    prompt: str,
    *,
    session_nonce: str,
    output_schema: dict[str, Any] | None,
) -> str:
    return build_agent_prompt(prompt, session_nonce=session_nonce, output_schema=output_schema)


def _default_python_workflow_template() -> str:
    return '''"""
type: workflow
description: Not implemented yet.
"""
from __future__ import annotations

import json

from myteam.workflows import run_agent


def main() -> None:
    result = run_agent(prompt="Not implemented yet. Tell the user.")
    print(json.dumps(result.to_jsonable()))


if __name__ == "__main__":
    main()
'''
