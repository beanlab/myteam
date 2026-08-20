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

from .. import templates
from ..prompt_rendering import render_prompt_text
from ..config import WorkflowDefaults, load_myteam_config, normalize_session_name
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
_INDICATOR_WIDTH = 44
_BLUE_BOLD = "\x1b[1;34m"
_RED_BOLD = "\x1b[1;31m"
_RESET = "\x1b[0m"


def run_agent(
    *,
    prompt: str,
    input: dict[str, Any] | None = None,
    output: dict[str, Any] | None = None,
    agent: str | None = None,
    session_name: str | None = None,
    model: str | None = None,
    reasoning: str | None = None,
    extra_args: tuple[str, ...] | list[str] | None = None,
    interactive: bool | None = None,
    session_id: str | None = None,
    fork: bool | None = None,
    prompt_source_path: Path | str | None = None,
) -> SessionResult:
    cwd = Path.cwd().resolve()
    defaults = _load_defaults(cwd)
    agent_name = _choose(agent, defaults.agent, DEFAULT_AGENT)
    effective_session_name = normalize_session_name(
        _choose(session_name, defaults.session_name, "New session")
    )
    assert effective_session_name is not None
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
    rendered_prompt = render_prompt_text(prompt, input or {}, source_path=prompt_source_path)
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
        session_closed = False
        end_started = False
        try:
            _emit_indicator(
                _format_start_indicator(
                    name=effective_session_name,
                    agent=agent_name,
                    model=effective_model,
                    reasoning=effective_reasoning,
                    interactive=bool(effective_interactive),
                    session_id=effective_session_id,
                    fork=bool(effective_fork),
                )
            )
            reported_result, exit_code = _forward_pty_until_complete(
                session,
                result_server,
                exit_sequence=runtime_config.exit_sequence,
            )
            try:
                _close_launched_session(session)
            finally:
                session_closed = True
            transcript = session.recording.snapshot()

            output_value = reported_result.output if reported_result is not None else None
            if reported_result is not None and reported_result.status != "ok":
                raise RuntimeError(json.dumps({"status": reported_result.status, "output": output_value}))

            native_session_id, usage = _resolve_session_metadata(runtime_config, session_nonce)
            result = SessionResult(
                exit_code=exit_code,
                output=output_value,
                usage=usage,
                transcript=transcript,
                session_id=native_session_id,
            )
            end_started = True
            _emit_indicator(_format_end_indicator(effective_session_name, result))
            return result
        except BaseException:
            if not session_closed:
                try:
                    _close_launched_session(session)
                except BaseException:
                    pass
            if not end_started:
                try:
                    _emit_indicator(_format_exception_end_indicator(effective_session_name))
                except BaseException:
                    pass
            raise


def _format_start_indicator(
    *,
    name: str,
    agent: str,
    model: str | None,
    reasoning: str | None,
    interactive: bool,
    session_id: str | None,
    fork: bool,
) -> bytes:
    title = "Session resumed" if session_id is not None and not fork else "Session started"
    first_fields = [f"name={_quote(name)}", f"agent={_quote(agent)}"]
    if session_id is not None:
        source_name = "forked_from" if fork else "session_id"
        first_fields.append(f"{source_name}={_quote(session_id)}")

    second_fields = []
    if model is not None:
        second_fields.append(f"model={_quote(model)}")
    if reasoning is not None:
        second_fields.append(f"reasoning={_quote(reasoning)}")
    second_fields.append(f"interactive={json.dumps(interactive)}")
    return _format_indicator(
        title,
        [" ".join(first_fields), " ".join(second_fields)],
        color=_BLUE_BOLD,
        leading_newline=False,
    )


def _format_end_indicator(name: str, result: SessionResult) -> bytes:
    metadata = [f"name={_quote(name)}"]
    if result.session_id is not None:
        metadata.append(f"session_id={_quote(result.session_id)}")
    color = _RED_BOLD if result.exit_code != 0 else _BLUE_BOLD
    return _format_indicator(
        "Session ended",
        [" ".join(metadata)],
        color=color,
        leading_newline=True,
    )


def _format_exception_end_indicator(name: str) -> bytes:
    return _format_indicator(
        "Session ended",
        [f"name={_quote(name)}"],
        color=_BLUE_BOLD,
        leading_newline=True,
    )


def _format_indicator(
    title: str,
    metadata: list[str],
    *,
    color: str,
    leading_newline: bool,
) -> bytes:
    top = f"┌─ {title} "
    top += "─" * max(1, _INDICATOR_WIDTH - len(top))
    bottom = "└" + "─" * (_INDICATOR_WIDTH - 1)
    plain = "NO_COLOR" in os.environ

    if plain:
        lines = [top, *(f"│ {line}" for line in metadata), bottom]
    else:
        lines = [
            f"{color}{top}{_RESET}",
            *(f"{color}│{_RESET} {line}" for line in metadata),
            f"{color}{bottom}{_RESET}",
        ]

    prefix = "\n" if leading_newline else ""
    return (prefix + "\n".join(lines) + "\n").encode("utf-8")


def _quote(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _emit_indicator(indicator: bytes) -> None:
    write_bytes(binary_output_stream(sys.stdout), indicator)


def _close_launched_session(session: ManagedPtyProcess) -> None:
    output = binary_output_stream(sys.stdout)
    try:
        if session.poll() is None:
            session.terminate()
        drain_pty_output(session, stdout_writer=lambda chunk: write_bytes(output, chunk))
    finally:
        session.close()


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
        result_instructions = render_prompt_text(
            templates.get_template("agent_result_instructions.md"),
            {
                # Don't sort the keys so the order the user provided is preserved
                "OUTPUT_SCHEMA_JSON": json.dumps(output_schema, indent=2),
            },
        ).strip()
        sections.append(result_instructions)

    return "\n\n".join(section for section in sections if section)


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
    """Forward the caller's terminal to an agent PTY until the agent exits."""

    reported_result: AgentReportedResult | None = None
    exit_deadline: float | None = None
    output = binary_output_stream(sys.stdout)

    def poll_result_channel() -> None:
        nonlocal reported_result, exit_deadline
        if reported_result is not None:
            return
        reported_result = result_server.wait_for_result(timeout=0)
        if reported_result is None:
            return
        _request_agent_exit(session, exit_sequence)
        exit_deadline = time.monotonic() + _AGENT_EXIT_TIMEOUT_SECONDS

    def stdout_writer(chunk: bytes) -> None:
        write_bytes(output, chunk)

    with RealTerminal(on_resize=session.resize) as terminal:
        session.resize(terminal.winsize())
        while True:
            poll_result_channel()

            code = session.poll()
            if code is not None:
                drain_pty_output(session, stdout_writer=stdout_writer)
                reported_result = _collect_reported_result(reported_result, result_server)
                return reported_result, code

            if exit_deadline is not None and time.monotonic() >= exit_deadline:
                session.terminate()
                exit_deadline = None
                continue

            activity = pump_pty_once(
                session,
                terminal,
                timeout=_AGENT_RESULT_POLL_SECONDS,
                stdout_writer=stdout_writer,
            )
            if activity.stdout_eof:
                try:
                    code = session.wait(timeout=0.1)
                except subprocess.TimeoutExpired:
                    code = session.poll()
                drain_pty_output(session, stdout_writer=stdout_writer)
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
