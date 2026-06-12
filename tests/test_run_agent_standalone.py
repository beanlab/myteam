from __future__ import annotations

import os
from pathlib import Path
import textwrap

from myteam.workflows import run_agent
from myteam.workflows.execution.protocol import ENV_SOCKET


def write_fake_agent_project(tmp_path: Path, script: str) -> None:
    (tmp_path / "fake_agent.py").write_text(textwrap.dedent(script), encoding="utf-8")
    (tmp_path / "fake_config.py").write_text(
        textwrap.dedent(
            """
            import sys

            class FakeAgentConfig:
                def build_argv(
                    self,
                    prompt_text,
                    model=None,
                    reasoning=None,
                    interactive=True,
                    session_id=None,
                    fork=False,
                    extra_args=None,
                ):
                    return [sys.executable, 'fake_agent.py', prompt_text]

                def get_exit_sequence(self):
                    return b'exit\\n'

                def locate_session_data(self, nonce, context):
                    return context.launch_cwd / 'native-session.txt'

                def get_session_id(self, session_data):
                    try:
                        return session_data.read_text(encoding='utf-8').strip()
                    except FileNotFoundError:
                        return 'missing-native-session'

                def get_usage_info(self, session_data):
                    return None
            """
        ),
        encoding="utf-8",
    )
    (tmp_path / ".myteam.yaml").write_text(
        "agents:\n  fake-agent: fake_config.py::FakeAgentConfig\n",
        encoding="utf-8",
    )


def test_run_agent_does_not_require_supervisor_and_returns_reported_output(tmp_path: Path, monkeypatch) -> None:
    write_fake_agent_project(
        tmp_path,
        """
        import os
        import sys
        from pathlib import Path
        from myteam.workflows.results import report_result
        from myteam.workflows.execution.protocol import ENV_AGENT_SESSION_NONCE, ENV_AGENT_SESSION_RESULT_SOCKET

        prompt = sys.argv[1]
        assert ENV_AGENT_SESSION_RESULT_SOCKET in os.environ
        Path('native-session.txt').write_text('native-123', encoding='utf-8')
        report_result({'prompt': prompt, 'nonce': os.environ[ENV_AGENT_SESSION_NONCE]})
        assert sys.stdin.readline() == 'exit\\n'
        """,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)

    result = run_agent(prompt="Hello {{ name }}", input={"name": "Ada"}, agent="fake-agent")

    assert result.exit_code == 0
    assert result.session_id == "native-123"
    assert result.output is not None
    assert "Hello Ada" in result.output["prompt"]
    assert "myteam result reporting" in result.output["prompt"]
    assert result.output["nonce"]


def test_run_agent_returns_none_output_for_clean_exit_without_result(tmp_path: Path, monkeypatch) -> None:
    write_fake_agent_project(
        tmp_path,
        """
        from pathlib import Path
        Path('native-session.txt').write_text('native-clean-exit', encoding='utf-8')
        print('clean exit transcript')
        """,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)

    result = run_agent(prompt="No result", agent="fake-agent")

    assert result.exit_code == 0
    assert result.output is None
    assert result.session_id == "native-clean-exit"
    assert "clean exit transcript" in result.transcript


def test_run_agent_populates_nonzero_exit_code_without_result(tmp_path: Path, monkeypatch) -> None:
    write_fake_agent_project(
        tmp_path,
        """
        import sys
        sys.exit(7)
        """,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)

    result = run_agent(prompt="No result", agent="fake-agent")

    assert result.exit_code == 7
    assert result.output is None


def test_run_agent_wraps_text_reported_by_myteam_result(tmp_path: Path, monkeypatch) -> None:
    write_fake_agent_project(
        tmp_path,
        """
        from myteam.workflows.results import report_result
        report_result('plain text result')
        """,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)

    result = run_agent(prompt="Report text", agent="fake-agent")

    assert result.exit_code == 0
    assert result.output == {"value": "plain text result"}
