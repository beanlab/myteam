from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys

from conftest import SRC
from myteam.workflows.agent_result_channel import AgentResultServer
from myteam.workflows.execution.protocol import ENV_AGENT_SESSION_RESULT_SOCKET


def run_myteam_with_input(project_dir: Path, *args: str, input_text: str = "", env: dict[str, str] | None = None):
    full_env = os.environ.copy()
    existing_pythonpath = full_env.get("PYTHONPATH")
    full_env["PYTHONPATH"] = str(SRC) if not existing_pythonpath else f"{SRC}{os.pathsep}{existing_pythonpath}"
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "myteam", *args],
        cwd=project_dir,
        env=full_env,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def test_result_reports_json_argument_to_managed_agent_session(tmp_path: Path) -> None:
    with AgentResultServer() as server:
        completed = run_myteam_with_input(
            tmp_path,
            "result",
            '{"answer": "ok"}',
            env={ENV_AGENT_SESSION_RESULT_SOCKET: server.socket_path},
        )
        reported = server.wait_for_result(timeout=1)

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert reported is not None
    assert reported.output == {"answer": "ok"}


def test_result_reads_stdin_for_managed_agent_session(tmp_path: Path) -> None:
    with AgentResultServer() as server:
        completed = run_myteam_with_input(
            tmp_path,
            "result",
            input_text='{"from": "stdin"}',
            env={ENV_AGENT_SESSION_RESULT_SOCKET: server.socket_path},
        )
        reported = server.wait_for_result(timeout=1)

    assert completed.returncode == 0
    assert reported is not None
    assert reported.output == {"from": "stdin"}


def test_result_preserves_non_json_text_for_managed_agent_session(tmp_path: Path) -> None:
    with AgentResultServer() as server:
        completed = run_myteam_with_input(
            tmp_path,
            "result",
            "plain text",
            env={ENV_AGENT_SESSION_RESULT_SOCKET: server.socket_path},
        )
        reported = server.wait_for_result(timeout=1)

    assert completed.returncode == 0
    assert reported is not None
    assert reported.output == "plain text"


def test_result_outside_managed_session_fails_clearly(run_myteam, tmp_path: Path) -> None:
    result = run_myteam(tmp_path, "result", '{"answer": "ok"}')

    assert result.exit_code != 0
    assert "No active myteam agent session" in result.stderr
