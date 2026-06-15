from __future__ import annotations

import json
from pathlib import Path
import textwrap

from myteam import run_agent


def write_recording_agent_project(tmp_path: Path) -> None:
    (tmp_path / "fake_agent.py").write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "from myteam.workflows.results import report_result\n"
        "Path('native-session.txt').write_text('native-session-from-fake', encoding='utf-8')\n"
        "report_result({'prompt': sys.argv[1]})\n"
        "assert sys.stdin.readline() == 'exit\\n'\n",
        encoding="utf-8",
    )
    (tmp_path / "fake_config.py").write_text(
        textwrap.dedent(
            """
            import json
            import sys
            from pathlib import Path

            class RecordingAgentConfig:
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
                    Path('observed-agent-settings.json').write_text(
                        json.dumps(
                            {
                                'model': model,
                                'reasoning': reasoning,
                                'interactive': interactive,
                                'session_id': session_id,
                                'fork': fork,
                                'extra_args': list(extra_args or []),
                            },
                            sort_keys=True,
                        ),
                        encoding='utf-8',
                    )
                    return [sys.executable, 'fake_agent.py', prompt_text]

                def get_exit_sequence(self):
                    return b'exit\\n'

                def locate_session_data(self, nonce, context):
                    return context.launch_cwd / 'native-session.txt'

                def get_session_id(self, session_data):
                    return session_data.read_text(encoding='utf-8')

                def get_usage_info(self, session_data):
                    return None
            """
        ).lstrip(),
        encoding="utf-8",
    )
    (tmp_path / ".myteam.yaml").write_text(
        "defaults:\n"
        "  agent: fake-agent\n"
        "  model: default-model\n"
        "  reasoning: low\n"
        "  interactive: false\n"
        "  session_id: default-session\n"
        "  fork: true\n"
        "  extra_args:\n"
        "    - --default\n"
        "agents:\n"
        "  fake-agent: fake_config.py::RecordingAgentConfig\n",
        encoding="utf-8",
    )


def read_observed_settings(tmp_path: Path) -> dict[str, object]:
    return json.loads((tmp_path / "observed-agent-settings.json").read_text(encoding="utf-8"))


def test_run_agent_applies_myteam_yaml_defaults(tmp_path: Path, monkeypatch) -> None:
    write_recording_agent_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = run_agent(prompt="Hello {{ name }}", input={"name": "Ada"})

    assert result.exit_code == 0
    assert result.session_id == "native-session-from-fake"
    assert result.output is not None
    assert "Hello Ada" in result.output["prompt"]
    assert read_observed_settings(tmp_path) == {
        "model": "default-model",
        "reasoning": "low",
        "interactive": False,
        "session_id": "default-session",
        "fork": True,
        "extra_args": ["--default"],
    }


def test_run_agent_explicit_arguments_override_myteam_yaml_defaults(tmp_path: Path, monkeypatch) -> None:
    write_recording_agent_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    run_agent(
        prompt="Override test",
        agent="fake-agent",
        model="explicit-model",
        reasoning="high",
        interactive=True,
        session_id="explicit-session",
        fork=False,
        extra_args=("--explicit", "value"),
    )

    assert read_observed_settings(tmp_path) == {
        "model": "explicit-model",
        "reasoning": "high",
        "interactive": True,
        "session_id": "explicit-session",
        "fork": False,
        "extra_args": ["--explicit", "value"],
    }


def test_run_agent_supplies_output_schema_content_to_agent_prompt_without_locking_wording(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_recording_agent_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = run_agent(
        prompt="Produce the answer.",
        output={"answer": "short answer"},
    )

    assert result.output is not None
    prompt = result.output["prompt"]
    assert "Produce the answer." in prompt
    assert "answer" in prompt
    assert "short answer" in prompt
