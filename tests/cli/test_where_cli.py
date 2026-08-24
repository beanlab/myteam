from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading

from myteam.workflows.execution.protocol import ENV_SOCKET, read_all


@contextmanager
def supervisor_response(tmp_path: Path, response: dict):
    socket_path = Path(f"/tmp/myteam-{os.getpid()}-{id(response)}.sock")
    socket_path.unlink(missing_ok=True)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(socket_path))
    server.listen(1)
    received: list[dict] = []

    def serve() -> None:
        try:
            connection, _ = server.accept()
        except OSError:
            return
        with connection:
            received.append(json.loads(read_all(connection).decode("utf-8")))
            connection.sendall(json.dumps(response).encode("utf-8"))

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield str(socket_path), received
    finally:
        server.close()
        thread.join(timeout=2)
        socket_path.unlink(missing_ok=True)


def write_agent_project(tmp_path: Path) -> None:
    (tmp_path / ".myteam.yaml").write_text(
        "agents:\n  fake-agent: fake_config.py::FakeAgentConfig\n",
        encoding="utf-8",
    )
    (tmp_path / "fake_config.py").write_text(
        "import sys\n"
        "class FakeAgentConfig:\n"
        "    def build_argv(self, prompt_text, model=None, reasoning=None, interactive=True, session_id=None, fork=False, extra_args=None):\n"
        "        return [sys.executable, 'fake_agent.py', prompt_text]\n"
        "    def get_exit_sequence(self): return b'exit\\n'\n"
        "    def locate_session_data(self, nonce, context): return context.launch_cwd / 'missing-session'\n"
        "    def get_session_id(self, session_data): return session_data.read_text(encoding='utf-8')\n"
        "    def get_usage_info(self, session_data): return None\n",
        encoding="utf-8",
    )
    (tmp_path / "fake_agent.py").write_text(
        "import json, subprocess, sys\n"
        "from myteam.workflows.results import report_result\n"
        "prompt = sys.argv[1]\n"
        "if 'START_CHILD' in prompt:\n"
        "    child = subprocess.run([sys.executable, '-m', 'myteam', 'start', 'child.py'], text=True, capture_output=True, check=True)\n"
        "    value = child.stdout\n"
        "elif 'WHERE' in prompt:\n"
        "    where = subprocess.run([sys.executable, '-m', 'myteam', 'where'], text=True, capture_output=True, check=True)\n"
        "    value = where.stdout\n"
        "else:\n"
        "    value = 'done'\n"
        "report_result(json.dumps(value))\n",
        encoding="utf-8",
    )


def write_result_workflow(path: Path, body: str) -> None:
    path.write_text(
        "from myteam.workflows import report_workflow_result, run_agent\n" + body,
        encoding="utf-8",
    )


def test_where_outside_managed_workflow_has_no_partial_output(tmp_path: Path) -> None:
    env = {
        **os.environ,
        "MYTEAM_AGENT_SESSION_NONCE": "standalone-agent",
        "MYTEAM_AGENT_SESSION_RESULT_SOCKET": str(tmp_path / "agent.sock"),
    }
    env.pop(ENV_SOCKET, None)
    completed = subprocess.run(
        [sys.executable, "-m", "myteam", "where"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert completed.stdout == ""
    assert "myteam start" in completed.stderr
    assert "managed" in completed.stderr.lower()


def test_where_help_and_argument_rejection(run_myteam, tmp_path: Path) -> None:
    help_result = run_myteam(tmp_path, "where", "--help")
    positional = run_myteam(tmp_path, "where", "extra")
    option = run_myteam(tmp_path, "where", "--json")

    assert help_result.exit_code == 0
    assert "usage: myteam where" in help_result.stdout
    for result in (positional, option):
        assert result.exit_code != 0
        assert result.stdout == ""
        assert "unrecognized arguments" in result.stderr


def test_where_formats_complete_stack_and_omits_unavailable_fields(
    run_myteam, tmp_path: Path, monkeypatch
) -> None:
    outer = str((tmp_path / "outer.py").resolve())
    inner = str((tmp_path / "inner.py").resolve())
    response = {
        "ok": True,
        "complete": True,
        "entries": [
            {"type": "workflow", "depth": 0, "workflow_path": outer},
            {
                "type": "agent",
                "depth": 1,
                "name": "Planner",
                "agent": "pi",
                "model": "model-x",
                "session_id": "native-1",
            },
            {"type": "workflow", "depth": 2, "workflow_path": inner},
            {"type": "agent", "depth": 3, "name": "Worker", "agent": "codex"},
        ],
    }
    with supervisor_response(tmp_path, response) as (socket_path, received):
        monkeypatch.setenv(ENV_SOCKET, socket_path)
        result = run_myteam(tmp_path, "where")

    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout == (
        f"{outer}\n"
        "  Planner (agent=pi, model=model-x, session_id=native-1)\n"
        f"    {inner}\n"
        "      Worker (agent=codex)\n"
    )
    assert received and received[0]["kind"] == "get_stack"


def test_where_escapes_control_characters(run_myteam, tmp_path: Path, monkeypatch) -> None:
    workflow_path = str((tmp_path / "line\nbreak").resolve())
    response = {
        "ok": True,
        "complete": True,
        "entries": [
            {"type": "workflow", "depth": 0, "workflow_path": workflow_path},
            {"type": "agent", "depth": 1, "name": "tab\tdel\x7fnext\x85", "agent": "pi"},
        ],
    }
    with supervisor_response(tmp_path, response) as (socket_path, _received):
        monkeypatch.setenv(ENV_SOCKET, socket_path)
        result = run_myteam(tmp_path, "where")

    assert result.exit_code == 0
    escaped_path = workflow_path.replace("\n", "\\n")
    assert result.stdout == f"{escaped_path}\n  tab\\tdel\\x7fnext\\x85 (agent=pi)\n"
    assert len(result.stdout.splitlines()) == 2


def test_where_rejects_incomplete_response_without_stdout(run_myteam, tmp_path: Path, monkeypatch) -> None:
    response = {
        "ok": True,
        "complete": False,
        "entries": [{"type": "workflow", "depth": 0, "workflow_path": "/tmp/partial.py"}],
    }
    with supervisor_response(tmp_path, response) as (socket_path, _received):
        monkeypatch.setenv(ENV_SOCKET, socket_path)
        result = run_myteam(tmp_path, "where")

    assert result.exit_code != 0
    assert result.stdout == ""
    assert result.stderr.strip()
    assert len(result.stderr.splitlines()) == 1


def test_where_rejects_unresolved_workflow_path_without_stdout(run_myteam, tmp_path: Path, monkeypatch) -> None:
    unresolved = str(tmp_path / "folder" / ".." / "workflow.py")
    response = {
        "ok": True,
        "complete": True,
        "entries": [{"type": "workflow", "depth": 0, "workflow_path": unresolved}],
    }
    with supervisor_response(tmp_path, response) as (socket_path, _received):
        monkeypatch.setenv(ENV_SOCKET, socket_path)
        result = run_myteam(tmp_path, "where")

    assert result.exit_code != 0
    assert result.stdout == ""
    assert len(result.stderr.splitlines()) == 1


def test_where_as_first_workflow_statement_reports_active_workflow(run_myteam, tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.py"
    workflow.write_text(
        "import subprocess, sys\n"
        "from myteam.workflows import report_workflow_result\n"
        "where = subprocess.run([sys.executable, '-m', 'myteam', 'where'], text=True, capture_output=True, check=True)\n"
        "report_workflow_result(where.stdout, end='')\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "start", str(workflow))

    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout == f"{workflow.resolve()}\n"


def test_where_from_immediate_managed_agent_shows_registration_without_unknown_id(
    run_myteam, tmp_path: Path
) -> None:
    write_agent_project(tmp_path)
    workflow = tmp_path / "agent.py"
    write_result_workflow(
        workflow,
        "result = run_agent(prompt='WHERE', agent='fake-agent', session_name='Immediate', model='model-x')\n"
        "report_workflow_result(result.output, end='')\n",
    )

    result = run_myteam(tmp_path, "start", str(workflow))

    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout == f"{workflow.resolve()}\n  Immediate (agent=fake-agent, model=model-x)\n"


def test_where_resumed_agent_shows_known_native_id(run_myteam, tmp_path: Path) -> None:
    write_agent_project(tmp_path)
    workflow = tmp_path / "resumed.py"
    write_result_workflow(
        workflow,
        "result = run_agent(prompt='WHERE', agent='fake-agent', session_name='Resumed', session_id='native-known')\n"
        "report_workflow_result(result.output, end='')\n",
    )

    result = run_myteam(tmp_path, "start", str(workflow))

    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout == f"{workflow.resolve()}\n  Resumed (agent=fake-agent, session_id=native-known)\n"


def test_where_excludes_completed_agent_from_later_session(run_myteam, tmp_path: Path) -> None:
    write_agent_project(tmp_path)
    workflow = tmp_path / "sequential.py"
    write_result_workflow(
        workflow,
        "run_agent(prompt='DONE', agent='fake-agent', session_name='Completed')\n"
        "result = run_agent(prompt='WHERE', agent='fake-agent', session_name='Current')\n"
        "report_workflow_result(result.output, end='')\n",
    )

    result = run_myteam(tmp_path, "start", str(workflow))

    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout == f"{workflow.resolve()}\n  Current (agent=fake-agent)\n"
    assert "Completed" not in result.stdout


def test_where_shows_agent_started_nested_workflow_and_session(run_myteam, tmp_path: Path) -> None:
    write_agent_project(tmp_path)
    child = tmp_path / "child.py"
    write_result_workflow(
        child,
        "result = run_agent(prompt='WHERE', agent='fake-agent', session_name='Child agent')\n"
        "report_workflow_result(result.output, end='')\n",
    )
    outer = tmp_path / "outer.py"
    write_result_workflow(
        outer,
        "result = run_agent(prompt='START_CHILD', agent='fake-agent', session_name='Parent agent')\n"
        "report_workflow_result(result.output, end='')\n",
    )

    result = run_myteam(tmp_path, "start", str(outer))

    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout == (
        f"{outer.resolve()}\n"
        "  Parent agent (agent=fake-agent)\n"
        f"    {child.resolve()}\n"
        "      Child agent (agent=fake-agent)\n"
    )


def test_where_shows_direct_nested_workflows_without_agent_entry(run_myteam, tmp_path: Path) -> None:
    child = tmp_path / "child.py"
    child.write_text(
        "import subprocess, sys\n"
        "from myteam.workflows import report_workflow_result\n"
        "where = subprocess.run([sys.executable, '-m', 'myteam', 'where'], text=True, capture_output=True, check=True)\n"
        "report_workflow_result(where.stdout, end='')\n",
        encoding="utf-8",
    )
    parent = tmp_path / "parent.py"
    parent.write_text(
        "from myteam.workflows import report_workflow_result, start_workflow\n"
        "report_workflow_result(start_workflow('child.py'), end='')\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "start", str(parent))

    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout == f"{parent.resolve()}\n  {child.resolve()}\n"


def test_where_unreachable_supervisor_has_no_stdout(run_myteam, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv(ENV_SOCKET, str(tmp_path / "stale.sock"))

    result = run_myteam(tmp_path, "where")

    assert result.exit_code != 0
    assert result.stdout == ""
    assert result.stderr.strip()
    assert len(result.stderr.splitlines()) == 1
