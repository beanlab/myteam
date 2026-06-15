from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
import sys
import time
from typing import Any, TypedDict

from .. import templates
from ..config import WorkflowDefaults
from ..templates import get_template_file
from .agent_session import build_agent_prompt
from .execution.mothership import Mothership
from .execution.protocol import (
    ENV_SOCKET,
    ENV_WORKFLOW_INVOCATION_ID,
    KIND_ACK_RESULT,
    KIND_POLL_RESULT,
    KIND_START_WORKFLOW,
    RpcClient,
)
from .results import SessionResult, UsageInfo


@dataclass(frozen=True)
class WorkflowProcessResult:
    exit_code: int
    result_text: str
    error_text: str = ""

    @property
    def stdout(self) -> str:
        """Compatibility alias for explicit workflow result text."""

        return self.result_text

    @property
    def stderr(self) -> str:
        """Compatibility alias for command/supervisor error text."""

        return self.error_text

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
        workflow_path.write_text(templates.get_template("new_workflow.py"), encoding=ENCODING)
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
    """Start a workflow invocation and return its explicit result text."""

    result = _start_workflow_result(
        workflow_name=workflow_name,
        args=args,
        workflow_input_json=workflow_input_json if workflow_input_json is not None else input,
    )
    return result.result_text


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
    _print_workflow_process_result(result)
    if result.exit_code != 0:
        raise SystemExit(result.exit_code)


def _start_workflow_result(
    *,
    workflow_name: str | None,
    args: tuple[str, ...],
    workflow_input_json: str | None,
) -> WorkflowProcessResult:
    argv = _build_workflow_argv(workflow_name, args, workflow_input_json)
    socket_path = os.environ.get(ENV_SOCKET)
    parent_session_id = os.environ.get(ENV_WORKFLOW_INVOCATION_ID)

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
        return WorkflowProcessResult(exit_code=1, result_text="", error_text="Workflow did not produce a result.\n")

    return _workflow_process_result_from_supervisor_result(result)


def _start_workflow_via_existing_mothership(
    *,
    socket_path: str,
    parent_session_id: str | None,
    argv: list[str],
    workflow_input_json: str | None,
) -> WorkflowProcessResult:
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

    return _workflow_process_result_from_supervisor_result(result)


def _workflow_process_result_from_supervisor_result(result: dict[str, Any]) -> WorkflowProcessResult:
    payload = result.get("result")
    if not isinstance(payload, dict):
        return WorkflowProcessResult(
            exit_code=1,
            result_text="",
            error_text=f"Invalid workflow result payload: {payload!r}\n",
        )

    if "exit_code" not in payload:
        message = payload.get("message")
        error_text = message if isinstance(message, str) else f"Invalid workflow result payload: {payload!r}"
        return WorkflowProcessResult(
            exit_code=1,
            result_text="",
            error_text=error_text + "\n",
        )

    exit_code = _coerce_exit_code(payload.get("exit_code"))
    result_text = payload.get("result_text")
    error_text = payload.get("error_text")
    return WorkflowProcessResult(
        exit_code=exit_code,
        result_text=result_text if isinstance(result_text, str) else "",
        error_text=error_text if isinstance(error_text, str) else "",
    )


def _print_workflow_process_result(result: WorkflowProcessResult) -> None:
    if result.result_text:
        print(result.result_text, end="", file=sys.stdout)
    if result.error_text:
        print(result.error_text, end="", file=sys.stderr)


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
        raise RuntimeError("myteam start requires a workflow file.")

    path = Path(target)
    if not path.exists():
        raise RuntimeError(f"Workflow '{target}' does not exist.")

    suffix = path.suffix.lower()
    absolute = str(path.resolve())
    if suffix == ".py":
        return [sys.executable, absolute, *args]
    if suffix == ".md":
        return [
            sys.executable,
            str(get_template_file("workflow_markdown_wrapper.py")),
            absolute,
            workflow_input_json or "{}",
            *args,
        ]
    raise RuntimeError(f"Workflow '{target}' has unsupported extension '{path.suffix}'.")


def _build_agent_prompt(
    prompt: str,
    *,
    session_nonce: str,
    output_schema: dict[str, Any] | None,
) -> str:
    return build_agent_prompt(prompt, session_nonce=session_nonce, output_schema=output_schema)

