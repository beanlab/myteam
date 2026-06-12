"""Standalone `run_agent` implementation.

`myteam start` supervises workflow processes. This module supervises one child
agent process for one `run_agent` call and owns the per-agent result channel
that `myteam result` reports to.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
from typing import Any

try:  # pragma: no cover - exercised when dependency is installed
    from jinja2 import Template
except ModuleNotFoundError:  # lightweight fallback for in-tree tests before deps are installed
    Template = None  # type: ignore[assignment]

from .. import templates
from ..config import WorkflowDefaults, load_myteam_config
from .agent_result_channel import AgentReportedResult, AgentResultServer
from .agents.registry import DEFAULT_AGENT
from .agents.runtime import AgentRuntimeConfig, AgentSessionContext, resolve_agent_runtime_config
from .execution.protocol import ENV_AGENT_SESSION_NONCE, ENV_AGENT_SESSION_RESULT_SOCKET
from .results import SessionResult, UsageInfo


_AGENT_RESULT_POLL_SECONDS = 0.05
_AGENT_EXIT_TIMEOUT_SECONDS = 2.0


def run_agent_session(
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
    cwd = Path.cwd().resolve()
    defaults = _load_defaults(cwd)
    agent_name = _choose(agent, defaults.agent, DEFAULT_AGENT)
    runtime_config = _resolve_runtime_config(agent_name, cwd)

    effective_model = _choose(model, defaults.model, None)
    effective_reasoning = _choose(reasoning, defaults.reasoning, None)
    effective_interactive = _choose(interactive, defaults.interactive, True)
    effective_session_id = _choose(session_id, defaults.session_id, None)
    effective_fork = _choose(fork, defaults.fork, False)
    effective_extra_args = _choose(extra_args, defaults.extra_args, None)
    if effective_extra_args is not None:
        effective_extra_args = tuple(str(item) for item in effective_extra_args)

    session_nonce = secrets.token_urlsafe(16)
    rendered_prompt = _render_prompt(prompt, input or {})
    agent_prompt = build_agent_prompt(
        rendered_prompt,
        session_nonce=session_nonce,
        output_schema=output,
    )
    argv = runtime_config.build_argv(
        agent_prompt,
        bool(effective_interactive),
        effective_session_id,
        bool(effective_fork),
        effective_model,
        effective_extra_args,
        effective_reasoning,
    )

    with AgentResultServer() as result_server:
        env = {
            **os.environ,
            ENV_AGENT_SESSION_RESULT_SOCKET: result_server.socket_path,
            ENV_AGENT_SESSION_NONCE: session_nonce,
        }
        process = subprocess.Popen(
            argv,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        transcript_parts: list[bytes] = []
        transcript_lock = threading.Lock()
        stdout_thread = _start_pipe_forwarder(process.stdout, _binary_output_stream(sys.stdout), transcript_parts, transcript_lock)
        stderr_thread = _start_pipe_forwarder(process.stderr, _binary_output_stream(sys.stderr), transcript_parts, transcript_lock)

        reported_result = _wait_for_report_or_exit(process, result_server)
        if reported_result is not None:
            _close_reported_agent_session(process, runtime_config.exit_sequence)
        exit_code = _wait_for_process(process)
        _join_reader(stdout_thread)
        _join_reader(stderr_thread)

    transcript = _decode_transcript(transcript_parts, transcript_lock)
    output_value = reported_result.output if reported_result is not None else None
    if output_value is not None and not isinstance(output_value, dict):
        output_value = {"value": output_value}
    if reported_result is not None and reported_result.status != "ok":
        raise RuntimeError(json.dumps({"status": reported_result.status, "output": output_value}))

    native_session_id, usage = _resolve_session_metadata(runtime_config, session_nonce)
    return SessionResult(
        exit_code=exit_code,
        output=output_value,
        usage=usage,
        transcript=transcript,
        session_id=native_session_id,
    )


def build_agent_prompt(
    prompt: str,
    *,
    session_nonce: str,
    output_schema: dict[str, Any] | None,
) -> str:
    result_instructions = templates.get_template("agent_result_instructions.md")
    output_schema_section = ""
    if output_schema is not None:
        output_schema_section = (
            "\nExpected result JSON shape:\n\n"
            "This describes the intended fields and structure for the result. "
            "Treat it as guidance for what to report with `myteam result`, not as a strict JSON Schema document.\n\n"
            "```json\n"
            f"{json.dumps(output_schema, indent=2, sort_keys=True)}\n"
            "```"
        )

    result_instructions = (
        result_instructions
        .replace("{{SESSION_NONCE}}", session_nonce)
        .replace("{{OUTPUT_SCHEMA_SECTION}}", output_schema_section)
        .strip()
    )
    return "\n\n".join((prompt.rstrip(), result_instructions))


def _render_prompt(prompt: str, input_values: dict[str, Any]) -> str:
    if not input_values:
        return prompt
    if Template is not None:
        return Template(prompt).render(**input_values)

    rendered = prompt
    for key, value in input_values.items():
        rendered = rendered.replace("{{ " + key + " }}", str(value))
        rendered = rendered.replace("{{" + key + "}}", str(value))
    return rendered


def _load_defaults(cwd: Path) -> WorkflowDefaults:
    config = load_myteam_config(cwd)
    if config is None:
        return WorkflowDefaults()
    return config.defaults


def _choose(explicit: Any, default: Any, fallback: Any) -> Any:
    if explicit is not None:
        return explicit
    if default is not None:
        return default
    return fallback


def _resolve_runtime_config(agent_name: str, cwd: Path) -> AgentRuntimeConfig:
    return resolve_agent_runtime_config(
        agent_name,
        project_root=cwd,
        session_context=AgentSessionContext(
            home=Path.home().resolve(),
            project_root=cwd,
            launch_cwd=cwd,
        ),
    )


class _TextStreamBinaryAdapter:
    def __init__(self, stream: Any) -> None:
        self.stream = stream

    def write(self, data: bytes) -> None:
        self.stream.write(data.decode("utf-8", errors="replace"))

    def flush(self) -> None:
        self.stream.flush()


def _binary_output_stream(stream: Any) -> Any:
    return stream.buffer if hasattr(stream, "buffer") else _TextStreamBinaryAdapter(stream)


def _start_pipe_forwarder(
    source: Any,
    destination: Any,
    transcript_parts: list[bytes],
    transcript_lock: threading.Lock,
) -> threading.Thread:
    def forward() -> None:
        if source is None:
            return
        while True:
            chunk = source.read(4096)
            if not chunk:
                return
            with transcript_lock:
                transcript_parts.append(chunk)
            try:
                destination.write(chunk)
                destination.flush()
            except Exception:
                pass

    thread = threading.Thread(target=forward, daemon=True)
    thread.start()
    return thread


def _wait_for_report_or_exit(
    process: subprocess.Popen[bytes],
    result_server: AgentResultServer,
) -> AgentReportedResult | None:
    while True:
        reported_result = result_server.wait_for_result(timeout=_AGENT_RESULT_POLL_SECONDS)
        if reported_result is not None:
            return reported_result
        if process.poll() is not None:
            return None


def _close_reported_agent_session(process: subprocess.Popen[bytes], exit_sequence: bytes) -> None:
    if process.poll() is not None:
        return
    if process.stdin is not None:
        try:
            process.stdin.write(exit_sequence)
            process.stdin.flush()
        except OSError:
            pass


def _wait_for_process(process: subprocess.Popen[bytes]) -> int:
    try:
        return process.wait(timeout=_AGENT_EXIT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            return process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            process.kill()
            return process.wait()


def _join_reader(thread: threading.Thread) -> None:
    thread.join(timeout=1)


def _decode_transcript(parts: list[bytes], lock: threading.Lock) -> str:
    with lock:
        data = b"".join(parts)
    return data.decode("utf-8", errors="replace")


def _resolve_session_metadata(
    runtime_config: AgentRuntimeConfig,
    session_nonce: str,
) -> tuple[str | None, list[UsageInfo]]:
    try:
        native_session_id, session_path = runtime_config.get_session_info(session_nonce)
    except Exception:
        return None, []

    usage: list[UsageInfo] = []
    if runtime_config.get_usage_info is not None:
        try:
            usage_info = runtime_config.get_usage_info(session_path)
        except Exception:
            usage_info = None
        if usage_info is not None:
            if isinstance(usage_info, list):
                usage.extend(item for item in usage_info if isinstance(item, UsageInfo))
            elif isinstance(usage_info, UsageInfo):
                usage.append(usage_info)
            elif isinstance(usage_info, dict):
                usage.append(UsageInfo(**usage_info))
    return native_session_id, usage
