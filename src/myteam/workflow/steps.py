from __future__ import annotations

import json
import os
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pyparsing import Literal

from .agents import resolve_agent_runtime_config
from .agents.runtime import AgentRuntimeConfig, AgentSessionContext
from .config import load_project_workflow_defaults
from .models import ProjectWorkflowDefaults, StepResult, UsageInfo, PreparedStep, RunState
from .usage import (
    print_aggregated_usage_summary,
    print_usage_summary,
    resolve_usage_session_path,
    resolve_usage_tracking,
)
from .validation.step_validation import validate_step_execution_args, validate_step_output
from .terminal.session import TerminalSessionResult, run_terminal_session
from ..disclosure import PROJECT_ROOT_ENV_VAR

_MISSING = object()

class AgentContext:
    def __init__(
        self,
        *,
        usage_logging: Literal["none", "summary", "per_model", "verbose"] | None = None,
        cwd: Path | str | None = None,
        inactivity_timeout_seconds: int | None = None,
    ) -> None:
        self.cwd = None if cwd is None else Path(cwd).resolve()
        self.project_root = _resolve_project_root(cwd=self.cwd)
        self.project_defaults: ProjectWorkflowDefaults | None = load_project_workflow_defaults(self.project_root)
        self.usage_logging = (
            usage_logging
            if usage_logging is not None
            else (self.project_defaults.usage_logging if self.project_defaults and self.project_defaults.usage_logging is not None else "summary")
        )
        self.timeout = (
            inactivity_timeout_seconds
            if inactivity_timeout_seconds is not None
            else (
                self.project_defaults.inactivity_timeout_seconds
                if self.project_defaults and self.project_defaults.inactivity_timeout_seconds is not None
                else 300
            )
        )
        self.launch_cwd = self.cwd if self.cwd is not None else self.project_root
        self.session_context = AgentSessionContext(
            home=Path.home().resolve(),
            project_root=self.project_root,
            launch_cwd=self.launch_cwd,
        )
        self._agent_configs: dict[str, AgentRuntimeConfig] = {}
        self._usage_totals_by_model: dict[str, UsageInfo] = {}

    def __enter__(self) -> "AgentContext":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self._usage_totals_by_model or self.usage_logging == "none":
            return
        self.print_usage()

    def run_agent(
        self,
        *,
        prompt: str,
        output: dict[str, Any] | None = None,
        input: Any = None,
        agent: str | None = None,
        model: str | None = None,
        interactive: Any = _MISSING,
        session_id: str | None = None,
        fork: Any = _MISSING,
        extra_args: Any = None,
    ) -> StepResult:
        state = RunState()
        if output is None:
            output = {}
        try:
            if output is None:
                output_template: dict[str, Any] = {}
            elif isinstance(output, dict):
                output_template = output
            else:
                raise StepExecutionError(
                    "argument_validation",
                    "Step definition field 'output' must be a mapping when provided.",
                )
            prepared = self._prepare_step(
                state=state,
                prompt=prompt,
                output_template=output_template,
                input=input,
                agent=agent,
                model=model,
                interactive=interactive,
                session_id=session_id,
                fork=fork,
                extra_args=extra_args,
            )
            session_result = self._run_prepared_step(state=state, prepared=prepared)
            return self._update_state(
                state=state,
                prepared=prepared,
                session_result=session_result,
            )
        except Exception as exc:
            return self._handle_run_agent_error(state=state, exc=exc)

    def _prepare_step(
        self,
        *,
        state: RunState,
        prompt: str,
        output_template: dict[str, Any],
        input: Any,
        agent: str | None,
        model: str | None,
        interactive: Any,
        session_id: str | None,
        fork: Any,
        extra_args: Any,
    ) -> PreparedStep:
        nonce = str(uuid.uuid4())
        state.nonce = nonce

        resolved_args = self._resolve_run_agent_args(
            input=input,
            agent=agent,
            model=model,
            interactive=interactive,
            session_id=session_id,
            fork=fork,
            extra_args=extra_args,
        )

        try:
            validate_step_execution_args(
                agent_name=resolved_args["agent"],
                interactive=resolved_args["interactive"],
                session_id=resolved_args["session_id"],
                fork=resolved_args["fork"],
                extra_args=resolved_args["extra_args"],
                model=resolved_args["model"],
            )
        except ValueError as exc:
            raise StepExecutionError("argument_validation", str(exc)) from exc

        agent_config = self._resolve_agent_config(resolved_args["agent"])
        state.agent_config = agent_config

        prompt_text = _build_step_prompt(
            resolved_input=resolved_args["input"],
            objective_text=prompt,
            output_template=output_template,
            session_nonce=nonce,
        )
        argv = _build_agent_argv(
            agent_config=agent_config,
            prompt_text=prompt_text,
            interactive=resolved_args["interactive"],
            session_id=resolved_args["session_id"],
            fork=resolved_args["fork"],
            model=resolved_args["model"],
            extra_args=resolved_args["extra_args"],
        )

        return PreparedStep(
            nonce=nonce,
            agent_config=agent_config,
            prompt_text=prompt_text,
            argv=argv,
            resolved_input=resolved_args["input"],
            output_template=output_template,
            agent_name=resolved_args["agent"],
            session_id=resolved_args["session_id"],
            fork=resolved_args["fork"],
        )

    def _run_prepared_step(
        self,
        *,
        state: RunState,
        prepared: PreparedStep,
    ) -> TerminalSessionResult:
        session_result = run_terminal_session(
            prepared.argv,
            exit_input=prepared.agent_config.exit_sequence,
            payload_validator=_build_payload_validator(prepared.output_template),
            cwd=self.launch_cwd,
            inactivity_timeout_seconds=self.timeout,
        )
        state.transcript = session_result.transcript
        return session_result

    def _update_state(
        self,
        *,
        state: RunState,
        prepared: PreparedStep,
        session_result: TerminalSessionResult,
    ) -> StepResult:
        """Validate output and update the state with session path and usage info"""
        if session_result.payload is None:
            raise StepExecutionError(
                "completion_missing",
                "Workflow agent exited before reporting a structured result.",
            )

        try:
            validate_step_output(prepared.output_template, session_result.payload)
        except ValueError as exc:
            raise StepExecutionError("output_validation", str(exc)) from exc

        discovered_session_id, session_path = _resolve_session_id(
            payload=session_result.payload,
            session_id=prepared.session_id,
            fork=prepared.fork,
            nonce=prepared.nonce,
            agent_config=prepared.agent_config,
        )
        state.session_path = session_path
        usage, usage_state, usage_error_message = resolve_usage_tracking(
            agent_config=prepared.agent_config,
            session_path=session_path,
        )
        self._set_usage_state(
            state=state,
            usage=usage,
            usage_state=usage_state,
            usage_error_message=usage_error_message,
        )
        self._record_usage(usage)
        self._print_usage(state)
        return StepResult(
            status="completed",
            output=session_result.payload,
            resolved_input=prepared.resolved_input,
            agent_name=prepared.agent_name,
            transcript=state.transcript,
            exit_code=session_result.exit_code,
            session_id=discovered_session_id,
            usage=state.usage,
            usage_state=state.usage_state,
            usage_error_message=state.usage_error_message,
        )

    def _handle_run_agent_error(
        self,
        *,
        state: RunState,
        exc: Exception,
    ) -> StepResult:
        if isinstance(exc, StepExecutionError):
            if exc.error_type in {"completion_missing", "output_validation", "session_discovery"}:
                self._collect_usage_after_failure(state=state)
                self._print_usage(state)
            return StepResult(
                status="failed",
                error_type=exc.error_type,
                error_message=exc.error_message,
                transcript=state.transcript,
                usage=state.usage,
                usage_state=state.usage_state,
                usage_error_message=state.usage_error_message,
            )
        if isinstance(exc, TimeoutError):
            self._collect_usage_after_failure(state=state)
            self._print_usage(state)
            return StepResult(
                status="failed",
                error_type="timeout",
                error_message=str(exc),
                transcript=state.transcript,
                usage=state.usage,
                usage_state=state.usage_state,
                usage_error_message=state.usage_error_message,
            )
        if isinstance(exc, OSError):
            return StepResult(
                status="failed",
                error_type="agent_launch",
                error_message=f"Failed to launch workflow agent: {exc}",
                transcript=state.transcript,
                usage_state="not_attempted",
            )
        raise exc

    def _resolve_agent_config(self, agent_name: str) -> AgentRuntimeConfig:
        cached_config = self._agent_configs.get(agent_name)
        if cached_config is not None:
            return cached_config
        try:
            config = resolve_agent_runtime_config(
                agent_name,
                project_root=self.project_root,
                session_context=self.session_context,
            )
        except KeyError as exc:
            raise StepExecutionError("agent_resolution", str(exc)) from exc
        self._agent_configs[agent_name] = config
        return config

    def _resolve_run_agent_args(
        self,
        *,
        input: Any,
        agent: str | None,
        model: str | None,
        interactive: Any,
        session_id: str | None,
        fork: Any,
        extra_args: Any,
    ) -> dict[str, Any]:
        resolved: dict[str, Any] = {
            "input": None,
            "agent": None,
            "model": None,
            "interactive": True,
            "session_id": None,
            "fork": False,
            "extra_args": None,
        }
        defaults = self.project_defaults
        if defaults is not None:
            if defaults.agent is not None:
                resolved["agent"] = defaults.agent
            if defaults.model is not None:
                resolved["model"] = defaults.model
            if defaults.interactive is not None:
                resolved["interactive"] = defaults.interactive
            if defaults.session_id is not None:
                resolved["session_id"] = defaults.session_id
            if defaults.fork is not None:
                resolved["fork"] = defaults.fork
            if defaults.extra_args is not None:
                resolved["extra_args"] = list(defaults.extra_args)

        if input is not None:
            resolved["input"] = input
        if agent is not None:
            resolved["agent"] = agent
        if model is not None:
            resolved["model"] = model
        if interactive is not _MISSING and interactive is not None:
            resolved["interactive"] = interactive
        if session_id is not None:
            resolved["session_id"] = session_id
        if fork is not _MISSING and fork is not None:
            resolved["fork"] = fork
        if extra_args is not None:
            resolved["extra_args"] = extra_args
        return resolved

    def _collect_usage_after_failure(
        self,
        *,
        state: RunState,
    ) -> None:
        if state.agent_config is None:
            return
        session_path = state.session_path
        if session_path is None:
            session_path = resolve_usage_session_path(
                agent_config=state.agent_config,
                nonce=state.nonce,
            )
        if session_path is None:
            return
        usage, usage_state, usage_error_message = resolve_usage_tracking(
            agent_config=state.agent_config,
            session_path=session_path,
        )
        self._set_usage_state(
            state=state,
            usage=usage,
            usage_state=usage_state,
            usage_error_message=usage_error_message,
        )
        self._record_usage(usage)

    def _set_usage_state(
        self,
        *,
        state: RunState,
        usage: UsageInfo | None,
        usage_state: str,
        usage_error_message: str | None,
    ) -> None:
        state.usage = usage
        state.usage_state = usage_state
        state.usage_error_message = usage_error_message

    def _record_usage(self, usage: UsageInfo | None) -> None:
        if usage is None:
            return
        totals = self._usage_totals_by_model.get(usage.model)
        if totals is None:
            totals = UsageInfo()
            self._usage_totals_by_model[usage.model] = totals
        totals.add(usage)

    def _print_usage(self, state: RunState) -> None:
        if state.usage is None or self.usage_logging != "verbose":
            return
        print_usage_summary(" Step Usage ".center(25, "-"), state.usage)

    def print_usage(self) -> None:
        print_aggregated_usage_summary(self._usage_totals_by_model, self.usage_logging)


def run_agent(
    *,
    prompt: str,
    output: dict[str, Any] | None = None,
    input: Any = None,
    agent: str | None = None,
    model: str | None = None,
    interactive: Any = _MISSING,
    session_id: str | None = None,
    fork: Any = _MISSING,
    extra_args: Any = None,
    cwd: Path | str | None = None,
) -> StepResult:
    """
    Execute one workflow step with an interactive agent runtime.

    Args:
        prompt: Objective text the agent should complete.
        output: Expected structured result shape the agent must report.
        input: Optional resolved input data included in the step prompt.
        agent: Workflow agent runtime name to launch.
        model: Optional model name forwarded to the agent adapter.
        interactive: Whether to launch the agent in interactive mode.
        session_id: Optional existing agent session to resume or fork.
        fork: Whether to fork ``session_id`` into a new session instead of resuming it.
        extra_args: Optional additional argv items passed to the agent adapter.
        cwd: Optional working directory for launching the agent process.
    """
    with AgentContext(cwd=cwd) as ctx:
        return ctx.run_agent(
            prompt=prompt,
            output=output,
            input=input,
            agent=agent,
            model=model,
            interactive=interactive,
            session_id=session_id,
            fork=fork,
            extra_args=extra_args,
        )


def _resolve_project_root(cwd: Path | None = None) -> Path:
    configured_agent_root = os.environ.get(PROJECT_ROOT_ENV_VAR)
    if configured_agent_root:
        return Path(configured_agent_root).resolve().parent

    if cwd is None:
        cwd = Path.cwd()

    cwd = cwd.resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / ".myteam").is_dir():
            return candidate
    return cwd


def _build_agent_argv(
    *,
    agent_config: AgentRuntimeConfig,
    prompt_text: str,
    interactive: bool,
    session_id: str | None,
    fork: bool,
    model: str | None,
    extra_args: list[str] | None,
) -> list[str]:
    try:
        argv = agent_config.build_argv(
            prompt_text,
            interactive,
            session_id,
            fork,
            model,
            extra_args=extra_args,
        )
    except Exception as exc:
        raise StepExecutionError(
            "agent_argv",
            f"Failed to build argv for workflow agent '{agent_config.name}': {exc}",
        ) from exc

    if not isinstance(argv, list) or any(not isinstance(item, str) for item in argv):
        raise StepExecutionError(
            "agent_argv",
            f"Workflow agent '{agent_config.name}' build_argv must return a list of strings.",
        )

    return argv


def _build_step_prompt(
    *,
    resolved_input: Any,
    objective_text: str,
    output_template: dict[str, Any] | None,
    session_nonce: str | None,
) -> str:
    sections = [
        "Complete the objective below.",
        "",
    ]
    if output_template:
        sections.extend([
            "Return the final workflow result by calling this command:",
            "Replace the placeholder values below with the real final result content.",
            "If the command reports an output format mismatch, correct the payload and try again.",
            "",
            "myteam workflow-result <<'JSON'",
            json.dumps(output_template, indent=2),
            "JSON",
            "",
            "Do not print result markers in the terminal.",
        ])
    if session_nonce is not None:
        sections.append(f"Session nonce: {session_nonce}")
    if resolved_input is not None:
        sections.extend(
            [
                "",
                "Input:",
                json.dumps(resolved_input, indent=2),
            ]
        )
    sections.extend(
        [
            "",
            "Objective:",
            objective_text,
        ]
    )
    return "\n".join(sections)


def _resolve_session_id(
    *,
    payload: Any,
    session_id: str | None,
    fork: bool,
    nonce: str | None,
    agent_config: AgentRuntimeConfig,
) -> tuple[str, Path | None] | None:
    if nonce is None:
        return None

    session_lookup_error: LookupError | None = None
    try:
        session_info = agent_config.get_session_info(nonce)
    except LookupError as exc:
        session_lookup_error = exc
        session_info = None

    payload_session_id = _extract_session_id(payload)
    if payload_session_id is not None:
        return payload_session_id, None if session_info is None else session_info[1]
    if session_id is not None and not fork:
        return session_id, None if session_info is None else session_info[1]
    if session_info is None:
        assert session_lookup_error is not None
        raise StepExecutionError("session_discovery", str(session_lookup_error)) from session_lookup_error
    return session_info


def _extract_session_id(output_value: Any) -> str | None:
    if not isinstance(output_value, dict):
        return None
    value = output_value.get("session_id")
    if isinstance(value, str) and value:
        return value
    return None


def _build_payload_validator(output_template: dict[str, Any]) -> Callable[[Any], str | None]:
    expected_output = json.dumps(output_template, indent=2)

    def validate(payload: Any) -> str | None:
        try:
            validate_step_output(output_template, payload)
        except ValueError:
            return "output format mismatch\nRequired output format:\n" + expected_output
        return None

    return validate


class StepExecutionError(Exception):
    def __init__(self, error_type: str, error_message: str) -> None:
        super().__init__(error_message)
        self.error_type = error_type
        self.error_message = error_message
