from __future__ import annotations

from pathlib import Path
from typing import Any

from myteam.disclosure import PROJECT_ROOT_ENV_VAR
from myteam.workflow.agents.runtime import AgentRuntimeConfig, AgentSessionContext
from myteam.workflow.definition.models import ProjectWorkflowDefaults, StepResult, UsageInfo
from myteam.workflow.execution.prompts import build_child_resume_prompt, build_step_prompt
from myteam.workflow.terminal.control_channel import ChildWorkflowRequest
from myteam.workflow.execution.steps import AgentContext, run_agent
from myteam.workflow.terminal.session import TerminalSessionResult
from myteam.workflow.execution.runner import NamedWorkflowRunResult


def fake_agent_config(*, session_id: str = "discovered-session") -> AgentRuntimeConfig:
    def build_argv(
        prompt_text: str,
        interactive: bool = True,
        session_id: str | None = None,
        fork: bool = False,
        model: str | None = None,
        extra_args: list[str] | None = None,
    ) -> list[str]:
        extras = extra_args or []
        if model is not None:
            extras = ["--model", model, *extras]
        if session_id is not None and fork:
            return ["codex", "fork", session_id, *extras, prompt_text]
        if session_id is not None:
            return ["codex", "resume", session_id, *extras, prompt_text]
        if not interactive:
            return ["codex", "exec", *extras, prompt_text]
        return ["codex", *extras, prompt_text]

    return AgentRuntimeConfig(
        name="codex",
        exec="codex",
        exit_sequence=b"/quit",
        get_session_info=lambda nonce: (session_id, Path("session.jsonl")),
        build_argv=build_argv,
        get_usage_info=lambda session_path: None,
        source="test",
    )


def recording_agent_config(seen: dict[str, Any], *, session_id: str = "discovered-session") -> AgentRuntimeConfig:
    def build_argv(
        prompt_text: str,
        interactive: bool = True,
        session_id: str | None = None,
        fork: bool = False,
        model: str | None = None,
        extra_args: list[str] | None = None,
    ) -> list[str]:
        seen["build_argv"] = {
            "prompt_text": prompt_text,
            "interactive": interactive,
            "session_id": session_id,
            "fork": fork,
            "model": model,
            "extra_args": extra_args,
        }
        extras = extra_args or []
        if model is not None:
            extras = ["--model", model, *extras]
        if session_id is not None and fork:
            return ["codex", "fork", session_id, *extras, prompt_text]
        if session_id is not None:
            return ["codex", "resume", session_id, *extras, prompt_text]
        if not interactive:
            return ["codex", "exec", *extras, prompt_text]
        return ["codex", *extras, prompt_text]

    return AgentRuntimeConfig(
        name="codex",
        exec="codex",
        exit_sequence=b"/quit",
        get_session_info=lambda nonce: (session_id, Path("session.jsonl")),
        build_argv=build_argv,
        get_usage_info=lambda session_path: None,
        source="test",
    )


def test_run_agent_wrapper_delegates_through_agent_context(monkeypatch, tmp_path):
    seen: dict[str, Any] = {}

    class FakeAgentContext:
        def __init__(self, *, cwd=None, inactivity_timeout_seconds=300):
            seen["init"] = (cwd, inactivity_timeout_seconds)

        def __enter__(self):
            seen["enter"] = True
            return self

        def __exit__(self, exc_type, exc, tb):
            seen["exit"] = (exc_type, exc)

        def run_agent(self, **kwargs):
            seen["kwargs"] = kwargs
            return StepResult(status="completed", output={"summary": "done"}, agent_name="codex")

    monkeypatch.setattr("myteam.workflow.execution.steps.AgentContext", FakeAgentContext)

    result = run_agent(
        agent="codex",
        cwd=tmp_path,
        prompt="Write a summary.",
        output={"summary": "short summary"},
        input={"topic": "release notes"},
        model="gpt-5.4",
        interactive=False,
        session_id="thread-123",
        fork=False,
        extra_args=["--exec", "pytest -q"],
    )

    assert result.status == "completed"
    assert seen["init"] == (tmp_path, 300)
    assert seen["enter"] is True
    assert seen["exit"] == (None, None)
    assert seen["kwargs"] == {
        "prompt": "Write a summary.",
        "output": {"summary": "short summary"},
        "input": {"topic": "release notes"},
        "agent": "codex",
        "model": "gpt-5.4",
        "interactive": False,
        "session_id": "thread-123",
        "fork": False,
        "extra_args": ["--exec", "pytest -q"],
    }


def test_agent_context_loads_project_defaults_once(monkeypatch, tmp_path):
    seen: dict[str, Any] = {"count": 0}
    monkeypatch.delenv(PROJECT_ROOT_ENV_VAR, raising=False)

    def fake_load_project_workflow_defaults(project_root: Path):
        seen["count"] += 1
        seen["project_root"] = project_root
        return ProjectWorkflowDefaults(agent="codex")

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        cwd,
        inactivity_timeout_seconds: int,
        payload_validator=None,
    ) -> TerminalSessionResult:
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    monkeypatch.setattr("myteam.workflow.execution.steps.load_project_workflow_defaults", fake_load_project_workflow_defaults)
    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: fake_agent_config())

    with AgentContext(cwd=tmp_path) as ctx:
        for _ in range(2):
            result = ctx.run_agent(
                prompt="Write a summary.",
                output={"summary": "short summary"},
            )
            assert result.status == "completed"

    assert seen["count"] == 1
    assert seen["project_root"] == tmp_path


def test_run_agent_uses_project_defaults(monkeypatch, tmp_path):
    monkeypatch.delenv(PROJECT_ROOT_ENV_VAR, raising=False)
    config_dir = tmp_path / ".myteam"
    config_dir.mkdir()
    (config_dir / ".config.yaml").write_text(
        "workflow_agent_defaults:\n"
        "  agent: codex\n"
        "  model: gpt-5.4\n"
        "  interactive: false\n"
        "  session_id: thread-123\n"
        "  fork: false\n"
        "  extra_args:\n"
        "    - --exec\n"
        "    - pytest -q\n",
        encoding="utf-8",
    )

    seen: dict[str, Any] = {}

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        cwd,
        inactivity_timeout_seconds: int,
        payload_validator=None,
    ) -> TerminalSessionResult:
        seen["argv"] = argv
        seen["cwd"] = cwd
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    def fake_resolve_agent_runtime_config(agent_name, **_kwargs):
        seen["agent_name"] = agent_name
        return recording_agent_config(seen)

    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", fake_resolve_agent_runtime_config)

    result = run_agent(
        cwd=tmp_path,
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "completed"
    assert seen["agent_name"] == "codex"
    assert seen["build_argv"] == {
        "prompt_text": seen["argv"][-1],
        "interactive": False,
        "session_id": "thread-123",
        "fork": False,
        "model": "gpt-5.4",
        "extra_args": ["--exec", "pytest -q"],
    }
    assert seen["argv"][0:4] == ["codex", "resume", "thread-123", "--model"]
    assert seen["cwd"] == tmp_path


def test_run_agent_explicit_none_falls_back_to_project_defaults(monkeypatch, tmp_path):
    monkeypatch.delenv(PROJECT_ROOT_ENV_VAR, raising=False)
    config_dir = tmp_path / ".myteam"
    config_dir.mkdir()
    (config_dir / ".config.yaml").write_text(
        "workflow_agent_defaults:\n"
        "  agent: codex\n"
        "  model: gpt-5.4\n"
        "  interactive: false\n"
        "  session_id: thread-123\n"
        "  fork: true\n"
        "  extra_args:\n"
        "    - --exec\n"
        "    - pytest -q\n",
        encoding="utf-8",
    )

    seen: dict[str, Any] = {}

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        cwd,
        inactivity_timeout_seconds: int,
        payload_validator=None,
    ) -> TerminalSessionResult:
        seen["argv"] = argv
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    def fake_resolve_agent_runtime_config(agent_name, **_kwargs):
        seen["agent_name"] = agent_name
        return recording_agent_config(seen)

    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", fake_resolve_agent_runtime_config)

    result = run_agent(
        cwd=tmp_path,
        agent="manual-agent",
        model="gpt-4.1",
        interactive=True,
        session_id=None,
        fork=False,
        extra_args=["--dry-run"],
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "completed"
    assert seen["agent_name"] == "manual-agent"
    assert seen["build_argv"] == {
        "prompt_text": seen["argv"][-1],
        "interactive": True,
        "session_id": "thread-123",
        "fork": False,
        "model": "gpt-4.1",
        "extra_args": ["--dry-run"],
    }
    assert seen["argv"][0:3] == ["codex", "resume", "thread-123"]
    assert "--model" in seen["argv"]
    assert "--dry-run" in seen["argv"]


def test_run_agent_defaults_missing_output_to_empty_mapping(monkeypatch, tmp_path):
    monkeypatch.delenv(PROJECT_ROOT_ENV_VAR, raising=False)

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        cwd,
        inactivity_timeout_seconds: int,
        payload_validator=None,
    ) -> TerminalSessionResult:
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={},
        )

    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: fake_agent_config())

    result = run_agent(
        cwd=tmp_path,
        agent="codex",
        prompt="Write a summary.",
        output=None,
    )

    assert result.status == "completed"
    assert result.output == {}


def test_agent_context_exit_calls_print_usage(monkeypatch):
    ctx = AgentContext()
    calls: list[str] = []
    ctx._usage_totals_by_model["gpt-5"] = UsageInfo(model="gpt-5")

    monkeypatch.setattr(ctx, "print_usage", lambda: calls.append("print"))

    assert ctx.__enter__() is ctx
    ctx.__exit__(None, None, None)

    assert calls == ["print"]


def test_agent_context_aggregates_usage_across_runs(monkeypatch, capsys):
    usages = iter(
        [
            UsageInfo(
                model="gpt-5-codex",
                input_tokens=1,
                cached_input_tokens=0,
                output_tokens=2,
                reasoning_output_tokens=3,
                total_tokens=4,
                estimated_cost=0.1,
            ),
            UsageInfo(
                model="gpt-5-codex",
                input_tokens=2,
                cached_input_tokens=1,
                output_tokens=3,
                reasoning_output_tokens=4,
                total_tokens=5,
                estimated_cost=0.2,
            ),
            UsageInfo(
                model="gpt-5.5",
                input_tokens=3,
                cached_input_tokens=2,
                output_tokens=4,
                reasoning_output_tokens=5,
                total_tokens=6,
                estimated_cost=0.3,
            ),
        ]
    )

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        payload_validator=None,
        cwd,
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    def fake_get_usage_info(_session_path: Path) -> UsageInfo | None:
        return next(usages)

    config = fake_agent_config()
    config = AgentRuntimeConfig(
        name=config.name,
        exec=config.exec,
        exit_sequence=config.exit_sequence,
        get_session_info=config.get_session_info,
        build_argv=config.build_argv,
        get_usage_info=fake_get_usage_info,
        source=config.source,
    )

    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: config)

    with AgentContext(usage_logging="verbose") as ctx:
        for _ in range(3):
            result = ctx.run_agent(
                agent="codex",
                prompt="Write a summary.",
                output={"summary": "short summary"},
            )
            assert result.status == "completed"

    captured = capsys.readouterr().out
    assert captured.count("Step Usage") == 3
    assert captured.count("Model: gpt-5-codex") == 3
    assert captured.count("Model: gpt-5.5") == 2
    assert "  Input: 3" in captured
    assert "Total:" in captured
    assert "  Input: 6" in captured
    assert "  Cost: $0.6000" in captured


def test_run_agent_returns_completed_result(monkeypatch):
    monkeypatch.setattr("myteam.workflow.execution.steps.load_project_workflow_defaults", lambda _project_root: None)
    seen: dict[str, Any] = {}

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        payload_validator=None,
        cwd,
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        seen["argv"] = argv
        seen["exit_input"] = exit_input
        seen["cwd"] = cwd
        seen["inactivity_timeout_seconds"] = inactivity_timeout_seconds
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: fake_agent_config())

    result = run_agent(
        agent="codex",
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "completed"
    assert result.output == {"summary": "done"}
    assert seen["argv"][0] == "codex"
    assert len(seen["argv"]) == 2
    assert "workflow-result" in seen["argv"][1]
    assert "Session nonce:" in seen["argv"][1]
    assert b"/quit" in seen["exit_input"]
    assert seen["cwd"] is not None
    assert result.session_id == "discovered-session"
    assert result.usage is None
    assert result.usage_state == "unavailable"


def test_build_step_prompt_includes_workflow_command_guidance():
    prompt = build_step_prompt(
        resolved_input={"feature_request": "Build X"},
        objective_text="Finish the parent task.",
        output_template={"summary": "short summary"},
        session_nonce="session-nonce-123",
    )

    assert "Session nonce: session-nonce-123" in prompt
    assert "myteam workflow-start <workflow> --session-nonce session-nonce-123" in prompt
    assert "myteam workflow-result --session-nonce session-nonce-123" in prompt
    assert "myteam workflow-result --session-nonce session-nonce-123 <<'JSON'" in prompt
    assert "Input:" in prompt
    assert "Objective:\nFinish the parent task." in prompt


def test_build_child_resume_prompt_includes_child_result_text():
    prompt = build_child_resume_prompt(
        child_workflow="child-workflow",
        child_result={"status": "completed", "output": {"summary": "done"}},
    )

    assert "child-workflow result:" in prompt


def test_run_agent_reuses_nonce_after_child_workflow_request(monkeypatch, tmp_path):
    monkeypatch.setattr("myteam.workflow.execution.steps.load_project_workflow_defaults", lambda _project_root: None)

    seen: dict[str, Any] = {"session_nonces": [], "prompts": []}

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        payload_validator=None,
        cwd,
        inactivity_timeout_seconds: int,
        session_nonce: str | None = None,
    ) -> TerminalSessionResult:
        seen["session_nonces"].append(session_nonce)
        seen["prompts"].append(argv[-1])
        if len(seen["session_nonces"]) == 1:
            return TerminalSessionResult(
                exit_code=0,
                transcript="parent transcript",
                payload=None,
                control_request=ChildWorkflowRequest(workflow="child", input={"topic": "docs"}),
            )
        return TerminalSessionResult(
            exit_code=0,
            transcript="resumed transcript",
            payload={"summary": "done"},
        )

    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: fake_agent_config())
    monkeypatch.setattr(
        "myteam.workflow.execution.runner.run_named_workflow",
        lambda _workflow, **_kwargs: NamedWorkflowRunResult(status="completed", output={"status": "completed"}),
    )

    result = run_agent(
        cwd=tmp_path,
        agent="codex",
        prompt="Finish the parent task.",
        output={"summary": "short summary"},
    )

    assert result.status == "completed"
    assert len(seen["session_nonces"]) == 2
    assert seen["session_nonces"][0] == seen["session_nonces"][1]
    assert seen["session_nonces"][0] is not None
    assert "child result:" in seen["prompts"][1]


def test_run_agent_marks_missing_usage_hook_as_not_implemented(monkeypatch, capsys):
    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        payload_validator=None,
        cwd,
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    config = fake_agent_config()
    config = AgentRuntimeConfig(
        name=config.name,
        exec=config.exec,
        exit_sequence=config.exit_sequence,
        get_session_info=config.get_session_info,
        build_argv=config.build_argv,
        source=config.source,
        get_usage_info=None,
    )
    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: config)

    result = run_agent(
        agent="codex",
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    captured = capsys.readouterr().out
    assert result.status == "completed"
    assert result.usage is None
    assert result.usage_state == "no_get_usage_info_implemented"
    assert result.usage_error_message == "workflow agent config does not implement get_usage_info"
    assert "Usage:" not in captured


def test_run_agent_reports_missing_result(monkeypatch):
    usage = UsageInfo(
        model="gpt-5-codex",
        input_tokens=14248,
        cached_input_tokens=0,
        output_tokens=144,
        reasoning_output_tokens=70,
        total_tokens=14392,
        estimated_cost=0.1234,
    )

    def fake_run_terminal_session(*_args, **_kwargs) -> TerminalSessionResult:
        return TerminalSessionResult(exit_code=0, transcript="runner transcript", payload=None)

    def fake_get_usage_info(_session_path: Path) -> UsageInfo | None:
        return usage

    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    config = fake_agent_config()
    config = AgentRuntimeConfig(
        name=config.name,
        exec=config.exec,
        exit_sequence=config.exit_sequence,
        get_session_info=config.get_session_info,
        build_argv=config.build_argv,
        get_usage_info=fake_get_usage_info,
        source=config.source,
    )
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: config)

    result = run_agent(
        agent="codex",
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "failed"
    assert result.error_type == "completion_missing"
    assert result.usage == usage
    assert result.usage_state == "collected"


def test_run_agent_does_not_print_step_usage_for_summary_logging_on_failure(monkeypatch, capsys):
    usage = UsageInfo(
        model="gpt-5-codex",
        input_tokens=10,
        cached_input_tokens=1,
        output_tokens=2,
        reasoning_output_tokens=3,
        total_tokens=13,
        estimated_cost=0.05,
    )

    def fake_run_terminal_session(*_args, **_kwargs) -> TerminalSessionResult:
        return TerminalSessionResult(exit_code=0, transcript="runner transcript", payload=None)

    def fake_get_usage_info(_session_path: Path) -> UsageInfo | None:
        return usage

    config = fake_agent_config()
    config = AgentRuntimeConfig(
        name=config.name,
        exec=config.exec,
        exit_sequence=config.exit_sequence,
        get_session_info=config.get_session_info,
        build_argv=config.build_argv,
        get_usage_info=fake_get_usage_info,
        source=config.source,
    )

    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: config)

    with AgentContext(usage_logging="summary") as ctx:
        result = ctx.run_agent(
            agent="codex",
            prompt="Write a summary.",
            output={"summary": "short summary"},
        )

    captured = capsys.readouterr().out
    assert result.status == "failed"
    assert "Step Usage" not in captured
    assert "Usage Summary" in captured
    assert "Total:" in captured


def test_run_agent_requires_explicit_agent(monkeypatch):
    monkeypatch.setattr("myteam.workflow.execution.steps.load_project_workflow_defaults", lambda _project_root: None)
    result = run_agent(
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "failed"
    assert result.error_type == "argument_validation"
    assert result.error_message == "Step definition is missing required string 'agent'."


def test_run_agent_preserves_literal_input(monkeypatch):
    monkeypatch.setattr("myteam.workflow.execution.steps.load_project_workflow_defaults", lambda _project_root: None)
    seen: dict[str, Any] = {}

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        payload_validator=None,
        cwd,
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        seen["argv"] = argv
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: fake_agent_config())

    result = run_agent(
        agent="codex",
        input={"topic": "release notes"},
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "completed"
    assert result.resolved_input == {"topic": "release notes"}
    assert '"topic": "release notes"' in seen["argv"][1]


def test_run_agent_passes_extra_args_to_build_argv(monkeypatch):
    seen: dict[str, Any] = {}

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        payload_validator=None,
        cwd,
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        seen["argv"] = argv
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: fake_agent_config())

    result = run_agent(
        agent="codex",
        model="gpt-5.4",
        extra_args=["--exec", "pytest -q"],
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "completed"
    assert seen["argv"][1:5] == ["--model", "gpt-5.4", "--exec", "pytest -q"]
    assert "workflow-result" in seen["argv"][5]


def test_run_agent_reports_invalid_extra_args(monkeypatch):
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: fake_agent_config())

    result = run_agent(
        agent="codex",
        extra_args=["--exec", 3],  # type: ignore[list-item]
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "failed"
    assert result.error_type == "argument_validation"
    assert result.error_message == "Step field 'extra_args[1]' must be a string."


def test_run_agent_reports_invalid_model(monkeypatch):
    calls: list[str] = []

    def fake_resolve_agent_runtime_config(*_args, **_kwargs):
        calls.append("called")
        return fake_agent_config()

    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", fake_resolve_agent_runtime_config)

    result = run_agent(
        agent="codex",
        model="",
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "failed"
    assert result.error_type == "argument_validation"
    assert result.error_message == "Step field 'model' must be a non-empty string when provided."
    assert calls == []


def test_run_agent_reports_build_argv_failure(monkeypatch):
    def failing_build_argv(
        _prompt_text,
        _interactive=True,
        _session_id=None,
        _fork=False,
        _model=None,
        extra_args=None,
    ):
        raise RuntimeError("bad argv")

    config = fake_agent_config()
    config = AgentRuntimeConfig(
        name=config.name,
        exec=config.exec,
        exit_sequence=config.exit_sequence,
        get_session_info=config.get_session_info,
        build_argv=failing_build_argv,
        get_usage_info=config.get_usage_info,
        source=config.source,
    )
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: config)

    result = run_agent(
        agent="codex",
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "failed"
    assert result.error_type == "agent_argv"
    assert result.error_message == "Failed to build argv for workflow agent 'codex': bad argv"


def test_run_agent_reports_invalid_argv_shape(monkeypatch):
    config = fake_agent_config()
    config = AgentRuntimeConfig(
        name=config.name,
        exec=config.exec,
        exit_sequence=config.exit_sequence,
        get_session_info=config.get_session_info,
        build_argv=lambda *_args, **_kwargs: ["codex", 1],  # type: ignore[list-item]
        get_usage_info=config.get_usage_info,
        source=config.source,
    )
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: config)

    result = run_agent(
        agent="codex",
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "failed"
    assert result.error_type == "agent_argv"
    assert result.error_message == "Workflow agent 'codex' build_argv must return a list of strings."


def test_run_agent_resumes_session_and_preserves_session_id(monkeypatch):
    monkeypatch.setattr("myteam.workflow.execution.steps.load_project_workflow_defaults", lambda _project_root: None)
    seen: dict[str, Any] = {}

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        payload_validator=None,
        cwd,
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        seen["argv"] = argv
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done", "session_id": "thread-123"},
        )

    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: fake_agent_config())

    result = run_agent(
        agent="codex",
        session_id="thread-123",
        prompt="Write a summary.",
        output={"summary": "short summary", "session_id": "agent session ID"},
    )

    assert result.status == "completed"
    assert result.session_id == "thread-123"
    assert seen["argv"][0:3] == ["codex", "resume", "thread-123"]
    assert "workflow-result" in seen["argv"][3]
    assert "Session nonce:" in seen["argv"][3]


def test_run_agent_forks_session_and_discovers_new_session_id(monkeypatch):
    monkeypatch.setattr("myteam.workflow.execution.steps.load_project_workflow_defaults", lambda _project_root: None)
    seen: dict[str, Any] = {}

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        payload_validator=None,
        cwd,
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        seen["argv"] = argv
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: fake_agent_config())

    result = run_agent(
        agent="codex",
        session_id="thread-123",
        fork=True,
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "completed"
    assert result.session_id == "discovered-session"
    assert seen["argv"][0:3] == ["codex", "fork", "thread-123"]
    assert "Session nonce:" in seen["argv"][3]


def test_run_agent_passes_interactive_false_to_build_argv(monkeypatch):
    seen: dict[str, Any] = {}

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        payload_validator=None,
        cwd,
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        seen["argv"] = argv
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: fake_agent_config())

    result = run_agent(
        agent="codex",
        interactive=False,
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "completed"
    assert seen["argv"][0:2] == ["codex", "exec"]


def test_run_agent_rejects_fork_without_session_id(monkeypatch):
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: fake_agent_config())

    result = run_agent(
        agent="codex",
        fork=True,
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "failed"
    assert result.error_type == "argument_validation"
    assert result.error_message == "Step field 'session_id' is required when 'fork' is true."


def test_run_agent_rejects_invalid_interactive(monkeypatch):
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: fake_agent_config())

    result = run_agent(
        agent="codex",
        interactive="yes",  # type: ignore[arg-type]
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "failed"
    assert result.error_type == "argument_validation"
    assert result.error_message == "Step field 'interactive' must be a boolean when provided."


def test_run_agent_rejects_invalid_fork(monkeypatch):
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: fake_agent_config())

    result = run_agent(
        agent="codex",
        fork="yes",  # type: ignore[arg-type]
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "failed"
    assert result.error_type == "argument_validation"
    assert result.error_message == "Step field 'fork' must be a boolean when provided."


def test_run_agent_rejects_empty_session_id(monkeypatch):
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: fake_agent_config())

    result = run_agent(
        agent="codex",
        session_id="",
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "failed"
    assert result.error_type == "argument_validation"
    assert result.error_message == "Step field 'session_id' must be a non-empty string when provided."


def test_run_agent_reports_session_discovery_failure(monkeypatch):
    usage = UsageInfo(
        model="gpt-5-codex",
        input_tokens=14248,
        cached_input_tokens=0,
        output_tokens=144,
        reasoning_output_tokens=70,
        total_tokens=14392,
        estimated_cost=0.1234,
    )

    def fake_run_terminal_session(*_args, **_kwargs) -> TerminalSessionResult:
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    def fake_get_usage_info(_session_path: Path) -> UsageInfo | None:
        return usage

    def missing_session_id(_nonce: str) -> str:
        raise LookupError("No session found")

    config = fake_agent_config()
    config = AgentRuntimeConfig(
        name=config.name,
        exec=config.exec,
        exit_sequence=config.exit_sequence,
        get_session_info=missing_session_id,
        build_argv=config.build_argv,
        get_usage_info=fake_get_usage_info,
        source=config.source,
    )
    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: config)

    result = run_agent(
        agent="codex",
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "failed"
    assert result.error_type == "session_discovery"
    assert result.error_message == "No session found"
    assert result.usage is None
    assert result.usage_state == "not_attempted"


def test_run_agent_attaches_usage_and_prints_summary(monkeypatch, capsys):
    usage = UsageInfo(
        model="gpt-5-codex",
        input_tokens=14248,
        cached_input_tokens=0,
        output_tokens=144,
        reasoning_output_tokens=70,
        total_tokens=14392,
        estimated_cost=0.1234,
    )

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        payload_validator=None,
        cwd,
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    def fake_get_usage_info(_session_path: Path) -> UsageInfo | None:
        return usage

    config = fake_agent_config()
    config = AgentRuntimeConfig(
        name=config.name,
        exec=config.exec,
        exit_sequence=config.exit_sequence,
        get_session_info=config.get_session_info,
        build_argv=config.build_argv,
        get_usage_info=fake_get_usage_info,
        source=config.source,
    )
    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: config)

    result = run_agent(
        agent="codex",
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    captured = capsys.readouterr().out
    assert result.status == "completed"
    assert result.usage == usage
    assert result.usage_state == "collected"
    assert "Usage Summary" in captured
    assert "Total:" in captured
    assert "Cost: $0.1234" in captured


def test_run_agent_records_unavailable_usage_lookup(monkeypatch, capsys):
    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        payload_validator=None,
        cwd,
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    def failing_get_usage_info(_session_path: Path):
        raise OSError("usage unavailable")

    config = fake_agent_config()
    config = AgentRuntimeConfig(
        name=config.name,
        exec=config.exec,
        exit_sequence=config.exit_sequence,
        get_session_info=config.get_session_info,
        build_argv=config.build_argv,
        get_usage_info=failing_get_usage_info,
        source=config.source,
    )
    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: config)

    result = run_agent(
        agent="codex",
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    captured = capsys.readouterr().out
    assert result.status == "completed"
    assert result.usage is None
    assert result.usage_state == "unavailable"
    assert result.usage_error_message == "usage unavailable"
    assert "Usage:" not in captured


def test_run_agent_attempts_usage_lookup_for_timeout(monkeypatch, capsys):
    usage = UsageInfo(
        model="gpt-5-codex",
        input_tokens=14248,
        cached_input_tokens=0,
        output_tokens=144,
        reasoning_output_tokens=70,
        total_tokens=14392,
        estimated_cost=0.1234,
    )

    def fake_run_terminal_session(*_args, **_kwargs):
        raise TimeoutError("timed out waiting for completion")

    def fake_get_usage_info(_session_path: Path) -> UsageInfo | None:
        return usage

    config = fake_agent_config()
    config = AgentRuntimeConfig(
        name=config.name,
        exec=config.exec,
        exit_sequence=config.exit_sequence,
        get_session_info=config.get_session_info,
        build_argv=config.build_argv,
        get_usage_info=fake_get_usage_info,
        source=config.source,
    )
    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: config)

    result = run_agent(
        agent="codex",
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    captured = capsys.readouterr().out
    assert result.status == "failed"
    assert result.error_type == "timeout"
    assert result.usage == usage
    assert result.usage_state == "collected"
    assert "Usage Summary" in captured


def test_run_agent_does_not_attempt_usage_lookup_before_launch(monkeypatch):
    calls: list[str] = []

    def fake_get_usage_info(_session_path: Path) -> UsageInfo | None:
        calls.append("usage")
        return None

    config = fake_agent_config()
    config = AgentRuntimeConfig(
        name=config.name,
        exec=config.exec,
        exit_sequence=config.exit_sequence,
        get_session_info=config.get_session_info,
        build_argv=config.build_argv,
        get_usage_info=fake_get_usage_info,
        source=config.source,
    )
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: config)

    result = run_agent(
        agent="codex",
        interactive="yes",  # type: ignore[arg-type]
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "failed"
    assert result.error_type == "argument_validation"
    assert result.usage is None
    assert result.usage_state == "not_attempted"
    assert calls == []


def test_run_agent_launches_from_project_root_when_called_under_active_root(tmp_path, monkeypatch):
    active_root = tmp_path / ".myteam"
    active_root.mkdir()
    monkeypatch.chdir(active_root)
    monkeypatch.setenv(PROJECT_ROOT_ENV_VAR, str(active_root))
    seen: dict[str, Any] = {}

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        payload_validator=None,
        cwd,
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        seen["cwd"] = cwd
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    def fake_resolve_agent_runtime_config(_agent, **kwargs):
        seen["project_root"] = kwargs["project_root"]
        seen["session_context"] = kwargs["session_context"]
        return fake_agent_config()

    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", fake_resolve_agent_runtime_config)

    result = run_agent(
        agent="codex",
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "completed"
    assert seen["cwd"] == tmp_path.resolve()
    assert seen["project_root"] == tmp_path.resolve()
    assert seen["session_context"] == AgentSessionContext(
        home=Path.home().resolve(),
        project_root=tmp_path.resolve(),
        launch_cwd=tmp_path.resolve(),
    )


def test_run_agent_resolves_project_root_from_requested_cwd(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    nested_cwd = workspace / "nested"
    workspace.mkdir()
    nested_cwd.mkdir()
    (workspace / ".myteam").mkdir()
    monkeypatch.delenv(PROJECT_ROOT_ENV_VAR, raising=False)
    monkeypatch.chdir(tmp_path)
    seen: dict[str, Any] = {}

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        payload_validator=None,
        cwd,
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        seen["cwd"] = cwd
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    def fake_resolve_agent_runtime_config(_agent, **kwargs):
        seen["project_root"] = kwargs["project_root"]
        seen["session_context"] = kwargs["session_context"]
        return fake_agent_config()

    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", fake_resolve_agent_runtime_config)

    result = run_agent(
        agent="codex",
        cwd=nested_cwd,
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "completed"
    assert seen["cwd"] == nested_cwd.resolve()
    assert seen["project_root"] == workspace.resolve()
    assert seen["session_context"] == AgentSessionContext(
        home=Path.home().resolve(),
        project_root=workspace.resolve(),
        launch_cwd=nested_cwd.resolve(),
    )


def test_run_agent_allows_launch_cwd_override(tmp_path, monkeypatch):
    active_root = tmp_path / ".myteam"
    requested_cwd = tmp_path / "workspace"
    active_root.mkdir()
    requested_cwd.mkdir()
    monkeypatch.chdir(active_root)
    monkeypatch.setenv(PROJECT_ROOT_ENV_VAR, str(active_root))
    seen: dict[str, Any] = {}

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        payload_validator=None,
        cwd,
        inactivity_timeout_seconds: int,
    ) -> TerminalSessionResult:
        seen["cwd"] = cwd
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"summary": "done"},
        )

    def fake_resolve_agent_runtime_config(_agent, **kwargs):
        seen["project_root"] = kwargs["project_root"]
        seen["session_context"] = kwargs["session_context"]
        return fake_agent_config()

    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", fake_resolve_agent_runtime_config)

    result = run_agent(
        agent="codex",
        cwd=requested_cwd,
        prompt="Write a summary.",
        output={"summary": "short summary"},
    )

    assert result.status == "completed"
    assert seen["cwd"] == requested_cwd.resolve()
    assert seen["project_root"] == tmp_path.resolve()
    assert seen["session_context"] == AgentSessionContext(
        home=Path.home().resolve(),
        project_root=tmp_path.resolve(),
        launch_cwd=requested_cwd.resolve(),
    )


def test_run_agent_runs_child_workflow_then_resumes_parent_session(monkeypatch, tmp_path):
    monkeypatch.delenv(PROJECT_ROOT_ENV_VAR, raising=False)
    (tmp_path / ".myteam").mkdir()
    seen: dict[str, Any] = {"terminal_calls": []}

    def get_session_info(nonce: str):
        seen["discovery_nonce"] = nonce
        return "parent-session", Path("session.jsonl")

    config = fake_agent_config(session_id="parent-session")
    config = AgentRuntimeConfig(
        name=config.name,
        exec=config.exec,
        exit_sequence=config.exit_sequence,
        get_session_info=get_session_info,
        build_argv=config.build_argv,
        get_usage_info=lambda _session_path: None,
        source=config.source,
    )

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        cwd,
        inactivity_timeout_seconds: int,
        payload_validator=None,
    ) -> TerminalSessionResult:
        seen["terminal_calls"].append(argv)
        if len(seen["terminal_calls"]) == 1:
            return TerminalSessionResult(
                exit_code=0,
                transcript="parent before child",
                payload=None,
                control_request=ChildWorkflowRequest(
                    workflow="development",
                    input={"feature_request": "Build X"},
                ),
            )
        return TerminalSessionResult(
            exit_code=0,
            transcript="parent after child",
            payload={"summary": "parent done"},
        )

    class ChildResult:
        status = "completed"
        output = {"answer": "child done"}
        error_message = None
        failed_step_name = None

    def fake_run_named_workflow(workflow: str, *, input=None):
        seen["child"] = (workflow, input)
        return ChildResult()

    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: config)
    monkeypatch.setattr("myteam.workflow.execution.runner.run_named_workflow", fake_run_named_workflow)

    result = run_agent(
        agent="codex",
        cwd=tmp_path,
        prompt="Finish the parent task.",
        output={"summary": "short summary"},
        model="gpt-5.4",
        extra_args=["--sandbox", "workspace-write"],
    )

    assert result.status == "completed"
    assert result.output == {"summary": "parent done"}
    assert result.session_id == "parent-session"
    assert seen["discovery_nonce"]
    assert seen["child"] == ("development", {"feature_request": "Build X"})
    assert len(seen["terminal_calls"]) == 2
    resume_argv = seen["terminal_calls"][1]
    assert resume_argv[:5] == ["codex", "resume", "parent-session", "--model", "gpt-5.4"]
    assert "--sandbox" in resume_argv
    resume_prompt = resume_argv[-1]
    assert "development result:" in resume_prompt


def test_run_agent_resumes_parent_with_child_failure_details(monkeypatch, tmp_path):
    monkeypatch.delenv(PROJECT_ROOT_ENV_VAR, raising=False)
    (tmp_path / ".myteam").mkdir()
    seen: dict[str, Any] = {}
    nonce_values = iter(["parent-nonce", "resume-nonce"])

    monkeypatch.setattr("myteam.workflow.execution.steps.uuid.uuid4", lambda: next(nonce_values))
    config = fake_agent_config(session_id="parent-session")

    def fake_run_terminal_session(
        argv: list[str],
        *,
        exit_input: bytes,
        cwd,
        inactivity_timeout_seconds: int,
        payload_validator=None,
    ) -> TerminalSessionResult:
        seen.setdefault("prompts", []).append(argv[-1])
        if len(seen["prompts"]) == 1:
            return TerminalSessionResult(
                exit_code=0,
                transcript="parent before child",
                payload=None,
                control_request=ChildWorkflowRequest(workflow="broken"),
            )
        return TerminalSessionResult(
            exit_code=0,
            transcript="parent after child",
            payload={"summary": "handled failure"},
        )

    class ChildResult:
        status = "failed"
        output = None
        error_message = "child exploded"
        failed_step_name = "step1"

    monkeypatch.setattr("myteam.workflow.execution.steps.run_terminal_session", fake_run_terminal_session)
    monkeypatch.setattr("myteam.workflow.execution.steps.resolve_agent_runtime_config", lambda _agent, **_kwargs: config)
    monkeypatch.setattr("myteam.workflow.execution.runner.run_named_workflow", lambda *_args, **_kwargs: ChildResult())

    result = run_agent(
        agent="codex",
        cwd=tmp_path,
        prompt="Finish the parent task.",
        output={"summary": "short summary"},
    )

    assert result.status == "completed"
    assert result.output == {"summary": "handled failure"}
    assert "child exploded" in seen["prompts"][1]
