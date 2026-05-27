from __future__ import annotations

import inspect
import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pyparsing import Literal

from ..agents import resolve_agent_runtime_config
from ..agents.runtime import AgentRuntimeConfig, AgentSessionContext
from ..definition.config import load_project_workflow_defaults
from ..definition.models import ProjectWorkflowDefaults, StepResult, UsageInfo, PreparedStep, RunState
from .errors import StepExecutionError
from .prompts import build_child_resume_prompt, build_step_prompt
from ..resolution.session_resolution import resolve_project_root, resolve_session_id
from .usage import (
    print_aggregated_usage_summary,
    print_usage_summary,
    resolve_usage_session_path,
    resolve_usage_tracking,
)
from ..validation import validate_step_execution_args, validate_step_output
from ..terminal.session import TerminalSessionResult, run_terminal_session
from ..terminal.control_channel import ChildWorkflowRequest

class AgentContext:
    def __init__(
        self,
        *,
        usage_logging: Literal["none", "summary", "per_model", "verbose"] | None = None,
        cwd: Path | str | None = None,
        inactivity_timeout_seconds: int | None = None,
    ) -> None:
        self.cwd = None if cwd is None else Path(cwd).resolve()
        self.project_root = resolve_project_root(cwd=self.cwd)
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
        interactive: bool | None = None,
        session_id: str | None = None,
        fork: bool | None = None,
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
            while session_result.control_request is not None:
                prepared = self._handle_child_workflow_request(
                    state=state,
                    prepared=prepared,
                    request=session_result.control_request,
                    original_output_template=output_template,
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
        interactive: bool | None,
        session_id: str | None,
        fork: bool | None,
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

        prompt_text = build_step_prompt(
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
            model=resolved_args["model"],
            interactive=resolved_args["interactive"],
            session_id=resolved_args["session_id"],
            fork=resolved_args["fork"],
            extra_args=resolved_args["extra_args"],
        )

    def _run_prepared_step(
        self,
        *,
        state: RunState,
        prepared: PreparedStep,
    ) -> TerminalSessionResult:
        session_result = run_terminal_session(
            prepared.argv,
            **self._terminal_session_kwargs(
                exit_input=prepared.agent_config.exit_sequence,
                cwd=self.launch_cwd,
                inactivity_timeout_seconds=self.timeout,
                session_nonce=prepared.nonce,
            ),
            payload_validator=_build_payload_validator(prepared.output_template),
        )
        if state.transcript:
            state.transcript = f"{state.transcript}\n{session_result.transcript}"
        else:
            state.transcript = session_result.transcript
        return session_result

    def _terminal_session_kwargs(
        self,
        *,
        exit_input: bytes,
        cwd: Path | str | None,
        inactivity_timeout_seconds: int,
        session_nonce: str | None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "exit_input": exit_input,
            "cwd": cwd,
            "inactivity_timeout_seconds": inactivity_timeout_seconds,
        }
        if session_nonce is None:
            return kwargs

        try:
            params = inspect.signature(run_terminal_session).parameters
        except (TypeError, ValueError):
            return kwargs

        if "session_nonce" in params or any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params.values()):
            kwargs["session_nonce"] = session_nonce
        return kwargs

    def _handle_child_workflow_request(
        self,
        *,
        state: RunState,
        prepared: PreparedStep,
        request: ChildWorkflowRequest,
        original_output_template: dict[str, Any],
    ) -> PreparedStep:
        parent_session_id, session_path = resolve_session_id(
            payload=None,
            session_id=prepared.session_id,
            fork=prepared.fork,
            nonce=prepared.nonce,
            agent_config=prepared.agent_config,
        )
        state.session_path = session_path

        from .runner import run_named_workflow

        try:
            child_result = run_named_workflow(request.workflow, input=request.input)
        except Exception as exc:
            child_payload = {
                "status": "failed",
                "error_message": str(exc),
            }
        else:
            child_payload = {
                "status": child_result.status,
                "output": child_result.output,
                "error_message": child_result.error_message,
                "failed_step_name": child_result.failed_step_name,
            }

        resume_prompt = build_child_resume_prompt(
            child_workflow=request.workflow,
            child_result=child_payload,
        )
        argv = _build_agent_argv(
            agent_config=prepared.agent_config,
            prompt_text=resume_prompt,
            interactive=prepared.interactive,
            session_id=parent_session_id,
            fork=False,
            model=prepared.model,
            extra_args=prepared.extra_args,
        )

        return PreparedStep(
            nonce=str(uuid.uuid4()),
            agent_config=prepared.agent_config,
            prompt_text=resume_prompt,
            argv=argv,
            resolved_input=prepared.resolved_input,
            output_template=original_output_template,
            agent_name=prepared.agent_name,
            model=prepared.model,
            interactive=prepared.interactive,
            session_id=parent_session_id,
            fork=False,
            extra_args=prepared.extra_args,
        )

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

        discovered_session_id, session_path = resolve_session_id(
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
        interactive: bool | None,
        session_id: str | None,
        fork: bool | None,
        extra_args: Any,
    ) -> dict[str, Any]:
        defaults = self.project_defaults
        default_agent = defaults.agent if defaults is not None and defaults.agent is not None else None
        default_model = defaults.model if defaults is not None and defaults.model is not None else None
        default_interactive = (
            defaults.interactive if defaults is not None and defaults.interactive is not None else True
        )
        default_session_id = defaults.session_id if defaults is not None and defaults.session_id is not None else None
        default_fork = defaults.fork if defaults is not None and defaults.fork is not None else False
        default_extra_args = (
            list(defaults.extra_args) if defaults is not None and defaults.extra_args is not None else None
        )

        return {
            "input": input,
            "agent": agent if agent is not None else default_agent,
            "model": model if model is not None else default_model,
            "interactive": interactive if interactive is not None else default_interactive,
            "session_id": session_id if session_id is not None else default_session_id,
            "fork": fork if fork is not None else default_fork,
            "extra_args": extra_args if extra_args is not None else default_extra_args,
        }

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
    interactive: bool | None = None,
    session_id: str | None = None,
    fork: bool | None = None,
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

def _build_payload_validator(output_template: dict[str, Any]) -> Callable[[Any], str | None]:
    expected_output = json.dumps(output_template, indent=2)

    def validate(payload: Any) -> str | None:
        try:
            validate_step_output(output_template, payload)
        except ValueError:
            return "output format mismatch\nRequired output format:\n" + expected_output
        return None

    return validate
