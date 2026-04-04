"""Workflow execution for deterministic myteam step orchestration."""
from __future__ import annotations

import json
import os
import queue
import shlex
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from . import __version__
from .loader import capture_loader_output
from .paths import AGENTS_DIRNAME, ENCODING, agents_root, base_dir
from .utils import is_role_dir

WORKFLOW_RUNS_DIRNAME = "workflow_runs"
WORKFLOW_SERVER_COMMAND_ENV_VAR = "MYTEAM_WORKFLOW_APP_SERVER_COMMAND"
DEFAULT_WORKFLOW_SERVER_COMMAND = "codex app-server"

WORKFLOW_DEVELOPER_INSTRUCTIONS = (
    "You are executing one deterministic myteam workflow step. "
    "Treat later user follow-up messages as additional guidance for this same step. "
    "Only return final structured JSON when explicitly asked to finalize the step. "
    "When finalizing, return only a JSON object matching the required outputs and do not wrap it in markdown fences."
)


class WorkflowError(RuntimeError):
    """Raised when a workflow cannot be loaded or executed."""


@dataclass(frozen=True)
class WorkflowStep:
    id: str
    role: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]


@dataclass(frozen=True)
class WorkflowDefinition:
    path: Path
    steps: list[WorkflowStep]


@dataclass
class WorkflowRunState:
    run_id: str
    workflow_path: str
    status: str
    next_step_index: int
    created_at: str
    updated_at: str
    current_step_id: str | None = None
    completed_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    attempts: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow_path": self.workflow_path,
            "status": self.status,
            "next_step_index": self.next_step_index,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "current_step_id": self.current_step_id,
            "completed_outputs": self.completed_outputs,
            "attempts": self.attempts,
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowRunState":
        return cls(
            run_id=str(data["run_id"]),
            workflow_path=str(data["workflow_path"]),
            status=str(data["status"]),
            next_step_index=int(data["next_step_index"]),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
            current_step_id=data.get("current_step_id"),
            completed_outputs=dict(data.get("completed_outputs", {})),
            attempts=dict(data.get("attempts", {})),
            last_error=data.get("last_error"),
        )


@dataclass
class PendingResponse:
    event: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    error: dict[str, Any] | None = None


class JsonRpcProcessClient:
    def __init__(self, command: str, *, cwd: Path):
        self.command = command
        self.cwd = cwd
        self.process: subprocess.Popen[str] | None = None
        self._request_id = 0
        self._write_lock = threading.Lock()
        self._pending: dict[int, PendingResponse] = {}
        self._pending_lock = threading.Lock()
        self._notifications: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stderr_lines: list[str] = []
        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None

    def __enter__(self) -> "JsonRpcProcessClient":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def start(self) -> None:
        args = shlex.split(self.command)
        if not args:
            raise WorkflowError("workflow app server command is empty")
        self.process = subprocess.Popen(
            args,
            cwd=self.cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        assert self.process.stdout is not None
        assert self.process.stderr is not None
        self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()

    def initialize(self) -> None:
        self.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "myteam",
                    "version": __version__,
                },
                "capabilities": {
                    "experimentalApi": True,
                },
            },
        )

    def close(self) -> None:
        if self.process is None:
            return
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        self.process = None

    def request(self, method: str, params: dict[str, Any], *, timeout: float = 30.0) -> Any:
        if self.process is None or self.process.stdin is None:
            raise WorkflowError("workflow app server process is not running")
        request_id = self._next_request_id()
        pending = PendingResponse()
        with self._pending_lock:
            self._pending[request_id] = pending
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        with self._write_lock:
            try:
                self.process.stdin.write(json.dumps(payload))
                self.process.stdin.write("\n")
                self.process.stdin.flush()
            except OSError as exc:
                raise WorkflowError(f"workflow app server is unavailable: {exc}") from exc
        if not pending.event.wait(timeout):
            with self._pending_lock:
                self._pending.pop(request_id, None)
            raise WorkflowError(f"timed out waiting for {method} response")
        if pending.error is not None:
            message = pending.error.get("message", f"{method} failed")
            raise WorkflowError(message)
        return pending.result

    def next_notification(self, *, timeout: float = 0.1) -> dict[str, Any] | None:
        try:
            return self._notifications.get(timeout=timeout)
        except queue.Empty:
            return None

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _read_stdout(self) -> None:
        assert self.process is not None
        assert self.process.stdout is not None
        for line in self.process.stdout:
            payload = line.strip()
            if not payload:
                continue
            try:
                message = json.loads(payload)
            except json.JSONDecodeError:
                self._stderr_lines.append(f"invalid JSON from workflow server: {payload}")
                continue
            if "id" in message:
                self._handle_response(message)
                continue
            if "method" in message:
                self._notifications.put(message)

    def _read_stderr(self) -> None:
        assert self.process is not None
        assert self.process.stderr is not None
        for line in self.process.stderr:
            self._stderr_lines.append(line.rstrip("\n"))

    def _handle_response(self, message: dict[str, Any]) -> None:
        response_id = message.get("id")
        if not isinstance(response_id, int):
            return
        with self._pending_lock:
            pending = self._pending.pop(response_id, None)
        if pending is None:
            return
        pending.result = message.get("result")
        pending.error = message.get("error")
        pending.event.set()


class UserInputPump:
    def __init__(self) -> None:
        self._queue: queue.Queue[str] = queue.Queue()
        self._thread: threading.Thread | None = None
        self.is_interactive = not sys.stdin.closed and sys.stdin.isatty()

    def start(self) -> None:
        # Interactive sessions should have exactly one stdin consumer: the
        # foreground prompt in the step interaction loop. The background reader
        # is only for non-interactive input such as tests or piped commands.
        if self.is_interactive or self._thread is not None or sys.stdin.closed:
            return
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def next_input(self) -> str | None:
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def wait_for_input(self, *, timeout: float | None = None) -> str | None:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _read_loop(self) -> None:
        for line in sys.stdin:
            text = line.rstrip("\n")
            if text:
                self._queue.put(text)


def workflow_start(path: str, app_server_command: str | None = None) -> None:
    workflow_path = _resolve_workflow_path(base_dir(), path)
    workflow = load_workflow_definition(workflow_path)
    run_state = create_run_state(base_dir(), workflow)
    _save_run_state(base_dir(), run_state)
    print(f"Starting workflow run {run_state.run_id}")
    _run_workflow(workflow, run_state, app_server_command=app_server_command)


def workflow_resume(run_id: str, app_server_command: str | None = None) -> None:
    run_state = load_run_state(base_dir(), run_id)
    workflow = load_workflow_definition(Path(run_state.workflow_path))
    print(f"Resuming workflow run {run_state.run_id}")
    _run_workflow(workflow, run_state, app_server_command=app_server_command)


def workflow_status(run_id: str) -> None:
    run_state = load_run_state(base_dir(), run_id)
    print(f"Run ID: {run_state.run_id}")
    print(f"Workflow: {run_state.workflow_path}")
    print(f"Status: {run_state.status}")
    if run_state.current_step_id:
        print(f"Current Step: {run_state.current_step_id}")
    print(f"Next Step Index: {run_state.next_step_index}")
    print("Completed Outputs:")
    if not run_state.completed_outputs:
        print("  (none)")
    else:
        print(json.dumps(run_state.completed_outputs, indent=2, sort_keys=True))
    if run_state.last_error:
        print(f"Last Error: {run_state.last_error}")


def load_workflow_definition(path: Path) -> WorkflowDefinition:
    try:
        loaded = yaml.safe_load(path.read_text(encoding=ENCODING))
    except OSError as exc:
        raise WorkflowError(f"failed to read workflow file {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise WorkflowError(f"failed to parse workflow YAML {path}: {exc}") from exc

    if not isinstance(loaded, dict) or not loaded:
        raise WorkflowError("workflow file must be a non-empty YAML mapping")

    steps: list[WorkflowStep] = []
    seen_steps: set[str] = set()
    for step_id, raw_step in loaded.items():
        if not isinstance(step_id, str) or not step_id:
            raise WorkflowError("workflow step names must be non-empty strings")
        if step_id in seen_steps:
            raise WorkflowError(f"duplicate workflow step '{step_id}'")
        if not isinstance(raw_step, dict):
            raise WorkflowError(f"workflow step '{step_id}' must be a mapping")
        role = raw_step.get("role")
        if not isinstance(role, str) or not role.strip():
            raise WorkflowError(f"workflow step '{step_id}' is missing a role")
        inputs = raw_step.get("inputs", {})
        outputs = raw_step.get("outputs")
        if inputs is None:
            inputs = {}
        if not isinstance(inputs, dict):
            raise WorkflowError(f"workflow step '{step_id}' inputs must be a mapping")
        if not isinstance(outputs, dict) or not outputs:
            raise WorkflowError(f"workflow step '{step_id}' outputs must be a non-empty mapping")
        _validate_output_names(step_id, outputs)
        _validate_input_references(step_id, inputs, seen_steps)
        steps.append(
            WorkflowStep(
                id=step_id,
                role=_normalize_role_path(role),
                inputs=inputs,
                outputs=outputs,
            )
        )
        seen_steps.add(step_id)

    return WorkflowDefinition(path=path, steps=steps)


def create_run_state(project_root: Path, workflow: WorkflowDefinition) -> WorkflowRunState:
    now = _utc_now()
    return WorkflowRunState(
        run_id=uuid.uuid4().hex[:12],
        workflow_path=str(workflow.path),
        status="in_progress",
        next_step_index=0,
        created_at=now,
        updated_at=now,
    )


def load_run_state(project_root: Path, run_id: str) -> WorkflowRunState:
    state_path = _run_dir(project_root, run_id) / "run.json"
    try:
        data = json.loads(state_path.read_text(encoding=ENCODING))
    except OSError as exc:
        raise WorkflowError(f"failed to read workflow run {run_id}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"workflow run {run_id} is invalid: {exc}") from exc
    return WorkflowRunState.from_dict(data)


def _run_workflow(
    workflow: WorkflowDefinition,
    run_state: WorkflowRunState,
    *,
    app_server_command: str | None,
) -> None:
    if run_state.status == "completed":
        print("Workflow already completed.")
        return

    command = app_server_command or os.environ.get(
        WORKFLOW_SERVER_COMMAND_ENV_VAR,
        DEFAULT_WORKFLOW_SERVER_COMMAND,
    )
    input_pump = UserInputPump()
    input_pump.start()

    try:
        with JsonRpcProcessClient(command, cwd=base_dir()) as client:
            client.initialize()
            for step_index in range(run_state.next_step_index, len(workflow.steps)):
                step = workflow.steps[step_index]
                run_state.status = "in_progress"
                run_state.current_step_id = step.id
                run_state.updated_at = _utc_now()
                _save_run_state(base_dir(), run_state)
                output = _run_step(client, step, run_state, input_pump)
                run_state.completed_outputs[step.id] = output
                run_state.next_step_index = step_index + 1
                run_state.current_step_id = None
                run_state.last_error = None
                run_state.updated_at = _utc_now()
                _save_run_state(base_dir(), run_state)
        run_state.status = "completed"
        run_state.updated_at = _utc_now()
        _save_run_state(base_dir(), run_state)
        print(f"Workflow {run_state.run_id} completed successfully.")
    except WorkflowError as exc:
        run_state.status = "failed"
        run_state.last_error = str(exc)
        run_state.updated_at = _utc_now()
        _save_run_state(base_dir(), run_state)
        print(f"Workflow {run_state.run_id} failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _run_step(
    client: JsonRpcProcessClient,
    step: WorkflowStep,
    run_state: WorkflowRunState,
    input_pump: UserInputPump,
) -> dict[str, Any]:
    role_instructions = _load_role_instructions(base_dir(), step.role)
    step_inputs = _resolve_inputs(step.inputs, run_state.completed_outputs)
    previous_outputs = {
        step_id: output
        for step_id, output in run_state.completed_outputs.items()
        if step_id != step.id
    }
    thread_result = client.request(
        "thread/start",
        {
            "cwd": str(base_dir()),
            "baseInstructions": role_instructions,
            "developerInstructions": WORKFLOW_DEVELOPER_INSTRUCTIONS,
            "serviceName": "myteam workflows",
        },
    )
    thread_id = thread_result["thread"]["id"]
    print(f"\n== Step {step.id} ==")
    print(f"thread: {thread_id}")
    attempt = {
        "thread_id": thread_id,
        "turn_id": None,
        "turn_ids": [],
        "status": "in_progress",
        "started_at": _utc_now(),
        "resolved_inputs": step_inputs,
        "final_message": None,
        "output": None,
        "error": None,
    }
    run_state.attempts.setdefault(step.id, []).append(attempt)
    _save_run_state(base_dir(), run_state)

    initial_message = _run_thread_turn(
        client,
        thread_id,
        _build_step_prompt(step, step_inputs, previous_outputs),
        attempt,
        run_state,
    )
    _enter_step_interaction_loop(
        client,
        step,
        thread_id,
        attempt,
        run_state,
        input_pump,
        initial_message,
    )
    final_message = _run_thread_turn(
        client,
        thread_id,
        _build_finalize_prompt(step, step_inputs, previous_outputs),
        attempt,
        run_state,
        output_schema=_build_output_schema(step.outputs),
    )

    output = _parse_step_output(final_message, step.outputs)
    attempt["status"] = "completed"
    attempt["final_message"] = final_message
    attempt["output"] = output
    attempt["finished_at"] = _utc_now()
    _save_run_state(base_dir(), run_state)
    print(f"Completed step {step.id}")
    return output


def _run_thread_turn(
    client: JsonRpcProcessClient,
    thread_id: str,
    text: str,
    attempt: dict[str, Any],
    run_state: WorkflowRunState,
    *,
    output_schema: dict[str, Any] | None = None,
) -> str:
    params = {
        "threadId": thread_id,
        "input": [
            {
                "type": "text",
                "text": text,
                "textElements": [],
            }
        ],
    }
    if output_schema is not None:
        params["outputSchema"] = output_schema

    turn_result = client.request("turn/start", params)
    turn_id = turn_result["turn"]["id"]
    attempt["turn_id"] = turn_id
    attempt["turn_ids"].append(turn_id)
    _save_run_state(base_dir(), run_state)
    print(f"turn: {turn_id}")
    return _await_turn_completion(client, turn_id, attempt, run_state)


def _await_turn_completion(
    client: JsonRpcProcessClient,
    turn_id: str,
    attempt: dict[str, Any],
    run_state: WorkflowRunState,
) -> str:
    latest_agent_message: str | None = None
    printed_delta = False

    while True:
        notification = client.next_notification(timeout=0.1)
        if notification is None:
            continue

        method = notification.get("method")
        params = notification.get("params", {})
        if method == "item/agentMessage/delta" and params.get("turnId") == turn_id:
            delta = params.get("delta", "")
            if delta:
                print(delta, end="", flush=True)
                printed_delta = True
        elif method == "item/completed" and params.get("turnId") == turn_id:
            item = params.get("item", {})
            if item.get("type") == "agentMessage":
                latest_agent_message = item.get("text")
        elif method == "error" and params.get("turnId") == turn_id:
            message = params.get("error", {}).get("message", "workflow step failed")
            attempt["status"] = "failed"
            attempt["error"] = message
            attempt["finished_at"] = _utc_now()
            _save_run_state(base_dir(), run_state)
            raise WorkflowError(message)
        elif method == "turn/completed" and params.get("turn", {}).get("id") == turn_id:
            turn_status = params.get("turn", {}).get("status")
            if printed_delta:
                print()
            if turn_status != "completed":
                message = f"workflow step ended with turn status {turn_status}"
                attempt["status"] = "failed"
                attempt["error"] = message
                attempt["finished_at"] = _utc_now()
                _save_run_state(base_dir(), run_state)
                raise WorkflowError(message)
            break

    if latest_agent_message is None:
        attempt["status"] = "failed"
        attempt["error"] = "workflow step completed without a final agent message"
        attempt["finished_at"] = _utc_now()
        _save_run_state(base_dir(), run_state)
        raise WorkflowError(attempt["error"])
    return latest_agent_message


def _enter_step_interaction_loop(
    client: JsonRpcProcessClient,
    step: WorkflowStep,
    thread_id: str,
    attempt: dict[str, Any],
    run_state: WorkflowRunState,
    input_pump: UserInputPump,
    initial_message: str,
) -> None:
    attempt["last_conversation_message"] = initial_message
    pending_message = input_pump.next_input()
    if not input_pump.is_interactive and pending_message is None:
        return

    print(f"[{step.id}] Type feedback to keep chatting on this thread. Type /done to finalize.")

    while True:
        follow_up = pending_message
        pending_message = None
        if follow_up is None:
            if input_pump.is_interactive:
                follow_up = input("> ").strip()
            else:
                follow_up = input_pump.wait_for_input(timeout=0.1)
                if follow_up is None:
                    return

        if not follow_up:
            continue
        if follow_up == "/done":
            return

        conversational_prompt = (
            "Continue working on the same workflow step. "
            "Do not finalize structured JSON yet.\n\n"
            f"User feedback:\n{follow_up}"
        )
        response = _run_thread_turn(client, thread_id, conversational_prompt, attempt, run_state)
        attempt["last_conversation_message"] = response


def _build_step_prompt(
    step: WorkflowStep,
    step_inputs: dict[str, Any],
    previous_outputs: dict[str, dict[str, Any]],
) -> str:
    payload = {
        "step": step.id,
        "inputs": step_inputs,
        "previous_outputs": previous_outputs,
        "required_outputs": step.outputs,
    }
    return (
        "Start working on this workflow step. "
        "You may ask questions or provide draft work, but do not finalize structured JSON yet.\n\n"
        f"{json.dumps(payload, indent=2, sort_keys=True)}"
    )


def _build_finalize_prompt(
    step: WorkflowStep,
    step_inputs: dict[str, Any],
    previous_outputs: dict[str, dict[str, Any]],
) -> str:
    payload = {
        "step": step.id,
        "inputs": step_inputs,
        "previous_outputs": previous_outputs,
        "required_outputs": step.outputs,
    }
    return (
        "Finalize this workflow step now. "
        "Return only a JSON object whose keys exactly match the required outputs.\n\n"
        f"{json.dumps(payload, indent=2, sort_keys=True)}"
    )


def _parse_step_output(message: str, outputs: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = json.loads(message)
    except json.JSONDecodeError as exc:
        stripped = _strip_json_fence(message)
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            raise WorkflowError(f"workflow step returned invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise WorkflowError("workflow step output must be a JSON object")
    expected_keys = set(outputs)
    actual_keys = set(parsed)
    if actual_keys != expected_keys:
        raise WorkflowError(
            f"workflow step output keys {sorted(actual_keys)} do not match required outputs {sorted(expected_keys)}"
        )
    return parsed


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text
    lines = stripped.splitlines()
    if len(lines) < 3:
        return text
    return "\n".join(lines[1:-1])


def _build_output_schema(outputs: dict[str, Any]) -> dict[str, Any]:
    properties = {
        name: _build_output_property_schema(description)
        for name, description in outputs.items()
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(outputs.keys()),
        "additionalProperties": False,
    }


def _build_output_property_schema(output_spec: Any) -> dict[str, Any]:
    # Keep the simple template.yaml shape ergonomic: a scalar output declaration
    # means "this key is a string result with this description".
    if isinstance(output_spec, dict):
        schema = dict(output_spec)
        schema_type = schema.get("type")
        if not isinstance(schema_type, str) or not schema_type:
            raise WorkflowError("workflow output schema mappings must include a non-empty 'type'")
        return schema

    return {
        "type": "string",
        "description": str(output_spec),
    }


def _resolve_inputs(inputs: dict[str, Any], completed_outputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        key: _resolve_input_value(value, completed_outputs)
        for key, value in inputs.items()
    }


def _resolve_input_value(value: Any, completed_outputs: dict[str, dict[str, Any]]) -> Any:
    if isinstance(value, dict):
        if set(value) == {"from"} and isinstance(value["from"], str):
            return _resolve_output_reference(value["from"], completed_outputs)
        return {
            key: _resolve_input_value(nested_value, completed_outputs)
            for key, nested_value in value.items()
        }
    if isinstance(value, list):
        return [_resolve_input_value(item, completed_outputs) for item in value]
    return value


def _resolve_output_reference(reference: str, completed_outputs: dict[str, dict[str, Any]]) -> Any:
    step_id, separator, output_name = reference.partition(".")
    if not separator or not output_name:
        raise WorkflowError(f"invalid workflow output reference '{reference}'")
    if step_id not in completed_outputs:
        raise WorkflowError(f"workflow output reference '{reference}' is not available yet")
    step_output = completed_outputs[step_id]
    if output_name not in step_output:
        raise WorkflowError(f"workflow output reference '{reference}' does not exist")
    return step_output[output_name]


def _validate_output_names(step_id: str, outputs: dict[str, Any]) -> None:
    seen_outputs: set[str] = set()
    for output_name in outputs:
        if not isinstance(output_name, str) or not output_name:
            raise WorkflowError(f"workflow step '{step_id}' has an invalid output name")
        if output_name in seen_outputs:
            raise WorkflowError(f"workflow step '{step_id}' has duplicate output '{output_name}'")
        seen_outputs.add(output_name)


def _validate_input_references(step_id: str, value: Any, seen_steps: set[str]) -> None:
    if isinstance(value, dict):
        if set(value) == {"from"} and isinstance(value["from"], str):
            ref_step_id, separator, _ = value["from"].partition(".")
            if not separator or ref_step_id not in seen_steps:
                raise WorkflowError(
                    f"workflow step '{step_id}' references unavailable output '{value['from']}'"
                )
            return
        for nested_value in value.values():
            _validate_input_references(step_id, nested_value, seen_steps)
    elif isinstance(value, list):
        for item in value:
            _validate_input_references(step_id, item, seen_steps)


def _load_role_instructions(project_root: Path, role_path: str) -> str:
    role_root = agents_root(project_root)
    folder = role_root if not role_path else role_root.joinpath(*role_path.split("/"))
    if not is_role_dir(folder):
        raise WorkflowError(f"workflow role '{role_path or AGENTS_DIRNAME}' is not a valid role")
    load_py = folder / "load.py"
    if not load_py.exists():
        raise WorkflowError(f"workflow role '{role_path or AGENTS_DIRNAME}' is missing load.py")
    try:
        return capture_loader_output(load_py, cwd=folder, project_root=role_root)
    except RuntimeError as exc:
        raise WorkflowError(f"failed to load workflow role '{role_path or AGENTS_DIRNAME}': {exc}") from exc


def _save_run_state(project_root: Path, run_state: WorkflowRunState) -> None:
    run_dir = _run_dir(project_root, run_state.run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    run_state.updated_at = _utc_now()
    (run_dir / "run.json").write_text(
        json.dumps(run_state.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding=ENCODING,
    )


def _run_dir(project_root: Path, run_id: str) -> Path:
    return agents_root(project_root) / WORKFLOW_RUNS_DIRNAME / run_id


def _resolve_workflow_path(project_root: Path, path: str) -> Path:
    workflow_path = Path(path)
    if not workflow_path.is_absolute():
        workflow_path = project_root / workflow_path
    return workflow_path.resolve()


def _normalize_role_path(role: str) -> str:
    normalized = role.strip()
    if normalized == AGENTS_DIRNAME:
        return ""
    if normalized.startswith(f"{AGENTS_DIRNAME}/"):
        return normalized.removeprefix(f"{AGENTS_DIRNAME}/")
    if normalized.startswith(f"./{AGENTS_DIRNAME}/"):
        return normalized.removeprefix(f"./{AGENTS_DIRNAME}/")
    return normalized


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
