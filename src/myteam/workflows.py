"""Workflow execution for deterministic myteam step orchestration."""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
from pathlib import Path
from typing import Any

from .loader import capture_loader_output
from .paths import AGENTS_DIRNAME, agents_root, base_dir
from .utils import is_role_dir
from .workflow_appserver import JsonRpcProcessClient
from .workflow_definition import (
    WorkflowDefinition,
    WorkflowError,
    WorkflowStep,
    build_output_schema,
    load_workflow_definition,
    parse_step_output,
    resolve_inputs,
)
from .workflow_runs import (
    WorkflowRunState,
    WorkflowStepAttempt,
    create_run_state,
    format_token_usage,
    load_run_state,
    save_run_state,
    utc_now,
    workflow_token_usage,
    zero_token_usage,
    add_token_usage,
)

WORKFLOW_SERVER_COMMAND_ENV_VAR = "MYTEAM_WORKFLOW_APP_SERVER_COMMAND"
DEFAULT_WORKFLOW_SERVER_COMMAND = "codex app-server"

WORKFLOW_DEVELOPER_INSTRUCTIONS = (
    "You are executing one deterministic myteam workflow step. "
    "Treat later user follow-up messages as additional guidance for this same step. "
    "Only return final structured JSON when explicitly asked to finalize the step. "
    "When finalizing, return only a JSON object matching the required outputs and do not wrap it in markdown fences."
)


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
    project_root = base_dir()
    workflow_path = _resolve_workflow_path(project_root, path)
    workflow = load_workflow_definition(workflow_path)
    run_state = create_run_state(workflow)
    save_run_state(project_root, run_state)
    print(f"Starting workflow run {run_state.run_id}")
    _run_workflow(project_root, workflow, run_state, app_server_command=app_server_command)


def workflow_resume(run_id: str, app_server_command: str | None = None) -> None:
    project_root = base_dir()
    run_state = load_run_state(project_root, run_id)
    workflow = load_workflow_definition(Path(run_state.workflow_path))
    print(f"Resuming workflow run {run_state.run_id}")
    _run_workflow(project_root, workflow, run_state, app_server_command=app_server_command)


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


def _run_workflow(
    project_root: Path,
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
        with JsonRpcProcessClient(command, cwd=project_root) as client:
            client.initialize()
            for step_index in range(run_state.next_step_index, len(workflow.steps)):
                step = workflow.steps[step_index]
                run_state.status = "in_progress"
                run_state.current_step_id = step.id
                run_state.updated_at = utc_now()
                save_run_state(project_root, run_state)
                output = _run_step(project_root, client, step, run_state, input_pump)
                run_state.completed_outputs[step.id] = output
                run_state.next_step_index = step_index + 1
                run_state.current_step_id = None
                run_state.last_error = None
                run_state.updated_at = utc_now()
                save_run_state(project_root, run_state)
        run_state.status = "completed"
        run_state.updated_at = utc_now()
        save_run_state(project_root, run_state)
        print(f"Workflow {run_state.run_id} completed successfully.")
        print(f"Workflow Tokens: {format_token_usage(workflow_token_usage(run_state))}")
    except WorkflowError as exc:
        run_state.status = "failed"
        run_state.last_error = str(exc)
        run_state.updated_at = utc_now()
        save_run_state(project_root, run_state)
        print(f"Workflow {run_state.run_id} failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _run_step(
    project_root: Path,
    client: JsonRpcProcessClient,
    step: WorkflowStep,
    run_state: WorkflowRunState,
    input_pump: UserInputPump,
) -> dict[str, Any]:
    role_instructions = _load_role_instructions(project_root, step.role)
    step_inputs = resolve_inputs(step.inputs, run_state.completed_outputs)
    previous_outputs = {
        step_id: output
        for step_id, output in run_state.completed_outputs.items()
        if step_id != step.id
    }
    thread_result = client.request(
        "thread/start",
        {
            "cwd": str(project_root),
            "baseInstructions": role_instructions,
            "developerInstructions": WORKFLOW_DEVELOPER_INSTRUCTIONS,
            "serviceName": "myteam workflows",
        },
    )
    thread_id = thread_result["thread"]["id"]
    print(f"\n== Step {step.id} ==")
    print(f"thread: {thread_id}")
    attempt = WorkflowStepAttempt(thread_id=thread_id, resolved_inputs=step_inputs)
    run_state.attempts.setdefault(step.id, []).append(attempt)
    save_run_state(project_root, run_state)

    initial_message = _run_thread_turn(
        project_root,
        client,
        thread_id,
        _build_step_prompt(step, step_inputs, previous_outputs),
        attempt,
        run_state,
    )
    _enter_step_interaction_loop(
        project_root,
        client,
        step,
        thread_id,
        attempt,
        run_state,
        input_pump,
        initial_message,
    )
    final_message = _run_thread_turn(
        project_root,
        client,
        thread_id,
        _build_finalize_prompt(step, step_inputs, previous_outputs),
        attempt,
        run_state,
        output_schema=build_output_schema(step.outputs),
    )

    output = parse_step_output(final_message, step.outputs)
    attempt.status = "completed"
    attempt.final_message = final_message
    attempt.output = output
    attempt.finished_at = utc_now()
    save_run_state(project_root, run_state)
    print(f"Completed step {step.id}")
    print(f"Step Tokens ({step.id}): {format_token_usage(attempt.token_usage)}")
    return output


def _run_thread_turn(
    project_root: Path,
    client: JsonRpcProcessClient,
    thread_id: str,
    text: str,
    attempt: WorkflowStepAttempt,
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
    attempt.turn_id = turn_id
    attempt.turn_ids.append(turn_id)
    save_run_state(project_root, run_state)
    print(f"turn: {turn_id}")
    return _await_turn_completion(project_root, client, turn_id, attempt, run_state)


def _await_turn_completion(
    project_root: Path,
    client: JsonRpcProcessClient,
    turn_id: str,
    attempt: WorkflowStepAttempt,
    run_state: WorkflowRunState,
) -> str:
    latest_agent_message: str | None = None
    latest_token_usage = zero_token_usage()
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
        elif method == "thread/tokenUsage/updated" and params.get("turnId") == turn_id:
            latest_token_usage = {
                "total_tokens": int(params.get("tokenUsage", {}).get("last", {}).get("totalTokens", 0)),
                "input_tokens": int(params.get("tokenUsage", {}).get("last", {}).get("inputTokens", 0)),
                "cached_input_tokens": int(params.get("tokenUsage", {}).get("last", {}).get("cachedInputTokens", 0)),
                "output_tokens": int(params.get("tokenUsage", {}).get("last", {}).get("outputTokens", 0)),
                "reasoning_output_tokens": int(
                    params.get("tokenUsage", {}).get("last", {}).get("reasoningOutputTokens", 0)
                ),
            }
        elif method == "error" and params.get("turnId") == turn_id:
            message = params.get("error", {}).get("message", "workflow step failed")
            attempt.status = "failed"
            attempt.error = message
            attempt.finished_at = utc_now()
            save_run_state(project_root, run_state)
            raise WorkflowError(message)
        elif method == "turn/completed" and params.get("turn", {}).get("id") == turn_id:
            turn_status = params.get("turn", {}).get("status")
            if printed_delta:
                print()
            if turn_status != "completed":
                message = f"workflow step ended with turn status {turn_status}"
                attempt.status = "failed"
                attempt.error = message
                attempt.finished_at = utc_now()
                save_run_state(project_root, run_state)
                raise WorkflowError(message)
            break

    if latest_agent_message is None:
        attempt.status = "failed"
        attempt.error = "workflow step completed without a final agent message"
        attempt.finished_at = utc_now()
        save_run_state(project_root, run_state)
        raise WorkflowError(attempt.error)
    attempt.token_usage = add_token_usage(attempt.token_usage, latest_token_usage)
    save_run_state(project_root, run_state)
    return latest_agent_message


def _enter_step_interaction_loop(
    project_root: Path,
    client: JsonRpcProcessClient,
    step: WorkflowStep,
    thread_id: str,
    attempt: WorkflowStepAttempt,
    run_state: WorkflowRunState,
    input_pump: UserInputPump,
    initial_message: str,
) -> None:
    attempt.last_conversation_message = initial_message
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
        response = _run_thread_turn(project_root, client, thread_id, conversational_prompt, attempt, run_state)
        attempt.last_conversation_message = response


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


def _resolve_workflow_path(project_root: Path, path: str) -> Path:
    workflow_path = Path(path)
    if not workflow_path.is_absolute():
        workflow_path = project_root / workflow_path
    return workflow_path.resolve()
