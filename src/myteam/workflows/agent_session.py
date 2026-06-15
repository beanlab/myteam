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
import time
from typing import Any

from jinja2 import Template

from .. import templates
from ..config import WorkflowDefaults, load_myteam_config
from .agent_result_channel import AgentReportedResult, AgentResultServer
from .agents.registry import DEFAULT_AGENT
from .agents.runtime import AgentRuntimeConfig, AgentSessionContext, resolve_agent_runtime_config
from .execution.protocol import ENV_AGENT_SESSION_NONCE, ENV_AGENT_SESSION_RESULT_SOCKET
from .execution.pty_forwarding import binary_output_stream, drain_pty_output, pump_pty_once, write_bytes
from .execution.pty_process import ManagedPtyProcess
from .execution.terminal import RealTerminal
from .results import SessionResult, UsageInfo


_AGENT_RESULT_POLL_SECONDS = 0.05
_AGENT_EXIT_TIMEOUT_SECONDS = 2.0


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
        session = ManagedPtyProcess.launch(
            session_id=session_nonce,
            request_id=session_nonce,
            argv=argv,
            env=env,
            cwd=str(cwd),
            winsize=RealTerminal().winsize(),
            nonce=session_nonce,
            agent_name=agent_name,
        )
        try:
            reported_result, exit_code = _forward_pty_until_complete(
                session,
                result_server,
                exit_sequence=runtime_config.exit_sequence,
            )
            transcript = session.recording.snapshot()
        finally:
            session.close()

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
    sections = [
        f"*Session ID: {session_nonce}*",
        prompt.rstrip(),
    ]

    if output_schema is not None:
        result_instructions = _render_prompt(
            templates.get_template("agent_result_instructions.md"),
            {
                # Don't sort the keys so the order the user provided is preserved
                "OUTPUT_SCHEMA_JSON": json.dumps(output_schema, indent=2),
            },
        ).strip()
        sections.append(result_instructions)

    return "\n\n".join(section for section in sections if section)


def _render_prompt(prompt: str, input_values: dict[str, Any]) -> str:
    if not input_values:
        return prompt
    return Template(prompt).render(**input_values)


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


def _forward_pty_until_complete(
    session: ManagedPtyProcess,
    result_server: AgentResultServer,
    *,
    exit_sequence: bytes,
) -> tuple[AgentReportedResult | None, int]:
    """Proxy the caller's terminal to an agent PTY while waiting for completion.

    This restores the old mothership behavior for agent sessions: the bytes read
    from the PTY master are both written to the caller's stdout and recorded by
    ``ManagedPtyProcess.read()`` for the session transcript. When the caller has
    an interactive stdin, input is forwarded into the child PTY as well.
    """

    reported_result: AgentReportedResult | None = None
    exit_deadline: float | None = None
    output = binary_output_stream(sys.stdout)

    def notice_reported_result() -> bool:
        nonlocal reported_result, exit_deadline
        if reported_result is None:
            reported_result = result_server.wait_for_result(timeout=0)
            if reported_result is not None:
                _request_agent_exit(session, exit_sequence)
                exit_deadline = time.monotonic() + _AGENT_EXIT_TIMEOUT_SECONDS
        return reported_result is not None

    def stdout_writer(chunk: bytes) -> None:
        # A result may arrive while select() is waiting for PTY output. Check the
        # result channel again immediately before visible forwarding so bytes
        # emitted after `myteam result` don't leak to the user's terminal.
        if not notice_reported_result():
            write_bytes(output, chunk)

    with RealTerminal(on_resize=session.resize) as terminal:
        session.resize(terminal.winsize())
        while True:
            notice_reported_result()

            code = session.poll()
            if code is not None:
                # After a result has been reported, shutdown/TUI cleanup bytes are
                # still recorded but no longer visibly forwarded. This keeps the
                # terminal clean after run_agent semantically completes.
                drain_pty_output(
                    session,
                    stdout_writer=stdout_writer,
                    forward_stdout=reported_result is None,
                )
                reported_result = _collect_reported_result(reported_result, result_server)
                return reported_result, code

            if exit_deadline is not None and time.monotonic() >= exit_deadline:
                session.terminate()
                continue

            activity = pump_pty_once(
                session,
                terminal,
                timeout=_AGENT_RESULT_POLL_SECONDS,
                stdout_writer=stdout_writer,
                forward_stdout=reported_result is None,
            )
            if activity.stdout_eof:
                code = session.poll()
                if code is None:
                    try:
                        code = session.wait(timeout=0.1)
                    except subprocess.TimeoutExpired:
                        code = 0
                reported_result = _collect_reported_result(reported_result, result_server)
                return reported_result, code if isinstance(code, int) else 0


def _collect_reported_result(
    reported_result: AgentReportedResult | None,
    result_server: AgentResultServer,
) -> AgentReportedResult | None:
    if reported_result is not None:
        return reported_result
    return result_server.wait_for_result(timeout=0.1)


def _request_agent_exit(session: ManagedPtyProcess, exit_sequence: bytes) -> None:
    if session.poll() is not None:
        return
    try:
        session.write(exit_sequence)
    except OSError:
        pass


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
