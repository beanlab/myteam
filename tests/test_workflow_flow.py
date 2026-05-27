from __future__ import annotations

import sys
from pathlib import Path

from myteam.disclosure import PROJECT_ROOT_ENV_VAR
from myteam.workflow.agents.runtime import AgentRuntimeConfig
from myteam.workflow.models import WorkflowRunResult
from myteam.workflow.terminal.session import TerminalSessionResult


def test_start_runs_workflow_from_yaml_file(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    workflow_file = initialized_project / ".myteam" / "demo.yaml"
    workflow_file.write_text(
        "step1:\n"
        "  prompt: hello\n"
        "  output:\n"
        "    message: hi\n",
        encoding="utf-8",
    )

    seen: dict[str, object] = {}

    def fake_load_workflow(path: Path):
        seen["path"] = path
        return {"step1": {"prompt": "hello", "output": {"message": "hi"}}}

    def fake_run_workflow(workflow_definition, **kwargs):
        seen["workflow"] = workflow_definition
        seen["kwargs"] = kwargs
        return WorkflowRunResult(
            status="completed",
            output={
                "step1": {
                    "prompt": "hello",
                    "agent": "codex",
                    "output": {"message": "hi"},
                }
            },
        )

    monkeypatch.setattr("myteam.commands.load_workflow", fake_load_workflow)
    monkeypatch.setattr("myteam.commands.run_workflow", fake_run_workflow)

    result = run_myteam_inprocess(initialized_project, "start", "demo")

    assert result.exit_code == 0
    assert result.stdout == ""
    assert result.stderr == ""
    assert seen["path"] == workflow_file
    assert seen["workflow"] == {"step1": {"prompt": "hello", "output": {"message": "hi"}}}
    assert callable(seen["kwargs"]["logger"])


def test_start_accepts_prefix_for_workflow_lookup(run_myteam_inprocess, tmp_path: Path, monkeypatch):
    workflow_root = tmp_path / ".agents"
    workflow_root.mkdir()
    workflow_file = workflow_root / "demo.yaml"
    workflow_file.write_text(
        "step1:\n"
        "  prompt: hello\n"
        "  output:\n"
        "    message: hi\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("myteam.commands.load_workflow", lambda path: {"step1": {"prompt": "hello", "output": {"message": "hi"}}})
    monkeypatch.setattr(
        "myteam.commands.run_workflow",
        lambda workflow_definition, **kwargs: WorkflowRunResult(status="completed", output={}),
    )

    result = run_myteam_inprocess(tmp_path, "start", "demo", "--prefix", ".agents")

    assert result.exit_code == 0
    assert workflow_file.exists()


def test_start_accepts_yml_extension(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    workflow_file = initialized_project / ".myteam" / "demo.yml"
    workflow_file.write_text(
        "step1:\n"
        "  prompt: hello\n"
        "  output:\n"
        "    message: hi\n",
        encoding="utf-8",
    )

    seen: dict[str, Path] = {}

    def fake_load_workflow(path: Path):
        seen["path"] = path
        return {"step1": {"prompt": "hello", "output": {"message": "hi"}}}

    monkeypatch.setattr("myteam.commands.load_workflow", fake_load_workflow)
    monkeypatch.setattr(
        "myteam.commands.run_workflow",
        lambda workflow_definition, **kwargs: WorkflowRunResult(status="completed", output={}),
    )

    result = run_myteam_inprocess(initialized_project, "start", "demo")

    assert result.exit_code == 0
    assert seen["path"] == workflow_file


def test_start_runs_python_workflow_file(run_myteam, initialized_project: Path):
    workflow_file = initialized_project / ".myteam" / "demo.py"
    workflow_file.write_text(
        "import os\n"
        "from pathlib import Path\n"
        "\n"
        "Path('workflow_ran.txt').write_text(\n"
        "    f\"cwd={Path.cwd()}\\nroot={os.environ.get('MYTEAM_PROJECT_ROOT')}\\n\",\n"
        "    encoding='utf-8',\n"
        ")\n",
        encoding="utf-8",
    )

    result = run_myteam(initialized_project, "start", "demo")

    assert result.exit_code == 0
    assert result.stdout == ""
    assert result.stderr == ""
    assert (initialized_project / ".myteam" / "workflow_ran.txt").read_text(encoding="utf-8") == (
        f"cwd={initialized_project / '.myteam'}\n"
        f"root={initialized_project / '.myteam'}\n"
    )


def test_start_passes_python_workflow_exit_code(run_myteam, initialized_project: Path):
    workflow_file = initialized_project / ".myteam" / "demo.py"
    workflow_file.write_text("raise SystemExit(7)\n", encoding="utf-8")

    result = run_myteam(initialized_project, "start", "demo")

    assert result.exit_code == 7
    assert result.stdout == ""
    assert result.stderr == ""


def test_start_runs_python_workflow_like_load_py(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    workflow_file = initialized_project / ".myteam" / "demo.py"
    workflow_file.write_text("VALUE = 1\n", encoding="utf-8")

    seen: dict[str, object] = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr("myteam.commands.subprocess.run", fake_run)

    result = run_myteam_inprocess(initialized_project, "start", "demo")

    assert result.exit_code == 0
    assert seen["args"] == [sys.executable, str(workflow_file)]
    assert seen["kwargs"]["cwd"] == workflow_file.parent
    assert seen["kwargs"]["check"] is False
    assert seen["kwargs"]["env"]["MYTEAM_PROJECT_ROOT"] == str(initialized_project / ".myteam")


def test_start_fails_when_workflow_file_is_missing(run_myteam_inprocess, initialized_project: Path):
    result = run_myteam_inprocess(initialized_project, "start", "missing")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Workflow 'missing' not found." in result.stderr


def test_start_fails_for_ambiguous_workflow_extensions(run_myteam_inprocess, initialized_project: Path):
    (initialized_project / ".myteam" / "demo.yaml").write_text("step1: {}\n", encoding="utf-8")
    (initialized_project / ".myteam" / "demo.yml").write_text("step1: {}\n", encoding="utf-8")

    result = run_myteam_inprocess(initialized_project, "start", "demo")

    assert result.exit_code == 1
    assert "Workflow 'demo' is ambiguous." in result.stderr


def test_start_reports_workflow_parse_failures(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    workflow_file = initialized_project / ".myteam" / "demo.yaml"
    workflow_file.write_text("step1: {}\n", encoding="utf-8")

    def fake_load_workflow(path: Path):
        raise ValueError("bad workflow")

    monkeypatch.setattr("myteam.commands.load_workflow", fake_load_workflow)

    result = run_myteam_inprocess(initialized_project, "start", "demo")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Failed to load workflow 'demo': bad workflow" in result.stderr


def test_start_reports_failed_step_from_engine(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    workflow_file = initialized_project / ".myteam" / "demo.yaml"
    workflow_file.write_text(
        "step1:\n"
        "  prompt: hello\n"
        "  output:\n"
        "    message: hi\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("myteam.commands.load_workflow", lambda path: {"step1": {"prompt": "hello", "output": {"message": "hi"}}})
    monkeypatch.setattr(
        "myteam.commands.run_workflow",
        lambda workflow_definition, **kwargs: WorkflowRunResult(
            status="failed",
            failed_step_name="step1",
            error_message="missing completion",
        ),
    )

    result = run_myteam_inprocess(initialized_project, "start", "demo")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Workflow 'demo' failed at step 'step1': missing completion" in result.stderr


def test_start_verbose_logs_to_stderr(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    workflow_file = initialized_project / ".myteam" / "demo.yaml"
    workflow_file.write_text(
        "step1:\n"
        "  prompt: hello\n"
        "  output:\n"
        "    message: hi\n",
        encoding="utf-8",
    )

    def fake_load_workflow(path: Path):
        return {"step1": {"prompt": "hello", "output": {"message": "hi"}}}

    def fake_run_workflow(workflow_definition, **kwargs):
        logger = kwargs["logger"]
        assert logger is not None
        logger("Starting step 'step1'")
        logger("Completed step 'step1'")
        return WorkflowRunResult(status="completed", output={})

    monkeypatch.setattr("myteam.commands.load_workflow", fake_load_workflow)
    monkeypatch.setattr("myteam.commands.run_workflow", fake_run_workflow)

    result = run_myteam_inprocess(initialized_project, "start", "demo", "--verbose")

    assert result.exit_code == 0
    assert result.stdout == ""
    assert "Resolved workflow 'demo' to" in result.stderr
    assert "Loaded workflow with 1 step(s)" in result.stderr
    assert "Starting step 'step1'" in result.stderr
    assert "Completed step 'step1'" in result.stderr
    assert "Workflow 'demo' completed successfully." in result.stderr


def test_start_uses_project_workflow_defaults_from_config(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    monkeypatch.delenv(PROJECT_ROOT_ENV_VAR, raising=False)
    (initialized_project / ".myteam" / ".config.yaml").write_text(
        "agent: codex\n"
        "model: gpt-5.4\n"
        "interactive: false\n"
        "session_id: thread-123\n"
        "fork: false\n"
        "extra_args:\n"
        "  - --exec\n"
        "  - pytest -q\n",
        encoding="utf-8",
    )
    (initialized_project / ".myteam" / "demo.yaml").write_text(
        "step1:\n"
        "  prompt: hello\n"
        "  output:\n"
        "    message: hi\n",
        encoding="utf-8",
    )

    seen: dict[str, object] = {}

    def fake_build_argv(
        prompt_text: str,
        interactive: bool = True,
        session_id: str | None = None,
        fork: bool = False,
        model: str | None = None,
        extra_args: list[str] | None = None,
    ) -> list[str]:
        seen["prompt_text"] = prompt_text
        seen["interactive"] = interactive
        seen["session_id"] = session_id
        seen["fork"] = fork
        seen["model"] = model
        seen["extra_args"] = extra_args
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

    def fake_get_session_info(_nonce: str) -> tuple[str, Path]:
        return "thread-123", initialized_project / ".myteam" / "session.jsonl"

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
        seen["exit_input"] = exit_input
        seen["payload_validator"] = payload_validator
        seen["inactivity_timeout_seconds"] = inactivity_timeout_seconds
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"message": "hi"},
        )

    monkeypatch.setattr(
        "myteam.workflow.steps.resolve_agent_runtime_config",
        lambda _agent, **_kwargs: AgentRuntimeConfig(
            name="codex",
            exec="codex",
            exit_sequence=b"/quit",
            get_session_info=fake_get_session_info,
            build_argv=fake_build_argv,
            source="test",
        ),
    )
    monkeypatch.setattr("myteam.workflow.steps.run_terminal_session", fake_run_terminal_session)

    result = run_myteam_inprocess(initialized_project, "start", "demo")

    assert result.exit_code == 0
    assert seen["argv"][0:4] == ["codex", "resume", "thread-123", "--model"]
    assert "--exec" in seen["argv"]
    assert "pytest -q" in seen["argv"]
    assert isinstance(seen["prompt_text"], str)
    assert seen["prompt_text"]
    assert seen["session_id"] == "thread-123"
    assert seen["fork"] is False
    assert seen["cwd"] == initialized_project
    assert seen["exit_input"] == b"/quit"
    assert seen["inactivity_timeout_seconds"] == 300


def test_start_prefers_step_values_over_project_defaults(run_myteam_inprocess, initialized_project: Path, monkeypatch):
    monkeypatch.delenv(PROJECT_ROOT_ENV_VAR, raising=False)
    (initialized_project / ".myteam" / ".config.yaml").write_text(
        "agent: codex\n"
        "model: gpt-5.4\n"
        "interactive: false\n"
        "session_id: thread-123\n"
        "fork: false\n"
        "extra_args:\n"
        "  - --exec\n"
        "  - pytest -q\n",
        encoding="utf-8",
    )
    (initialized_project / ".myteam" / "demo.yaml").write_text(
        "step1:\n"
        "  agent: codex\n"
        "  model: gpt-4.1\n"
        "  interactive: false\n"
        "  session_id: step-session\n"
        "  fork: true\n"
        "  extra_args:\n"
        "    - --dry-run\n"
        "  prompt: hello\n"
        "  output:\n"
        "    message: hi\n",
        encoding="utf-8",
    )

    seen: dict[str, object] = {}

    def fake_build_argv(
        prompt_text: str,
        interactive: bool = True,
        session_id: str | None = None,
        fork: bool = False,
        model: str | None = None,
        extra_args: list[str] | None = None,
    ) -> list[str]:
        seen["prompt_text"] = prompt_text
        seen["interactive"] = interactive
        seen["session_id"] = session_id
        seen["fork"] = fork
        seen["model"] = model
        seen["extra_args"] = extra_args
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

    def fake_get_session_info(_nonce: str) -> tuple[str, Path]:
        return "step-session", initialized_project / ".myteam" / "session.jsonl"

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
        seen["exit_input"] = exit_input
        seen["payload_validator"] = payload_validator
        seen["inactivity_timeout_seconds"] = inactivity_timeout_seconds
        return TerminalSessionResult(
            exit_code=0,
            transcript="runner transcript",
            payload={"message": "hi"},
        )

    monkeypatch.setattr(
        "myteam.workflow.steps.resolve_agent_runtime_config",
        lambda _agent, **_kwargs: AgentRuntimeConfig(
            name="codex",
            exec="codex",
            exit_sequence=b"/quit",
            get_session_info=fake_get_session_info,
            build_argv=fake_build_argv,
            source="test",
        ),
    )
    monkeypatch.setattr("myteam.workflow.steps.run_terminal_session", fake_run_terminal_session)

    result = run_myteam_inprocess(initialized_project, "start", "demo")

    assert result.exit_code == 0
    assert seen["argv"][0:3] == ["codex", "fork", "step-session"]
    assert "--model" in seen["argv"]
    assert "gpt-4.1" in seen["argv"]
    assert "--dry-run" in seen["argv"]
    assert seen["interactive"] is False
    assert seen["session_id"] == "step-session"
    assert seen["fork"] is True
    assert isinstance(seen["prompt_text"], str)
    assert seen["prompt_text"]
