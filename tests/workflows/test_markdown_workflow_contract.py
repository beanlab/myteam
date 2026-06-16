from __future__ import annotations

import json
from pathlib import Path
import textwrap


def write_markdown_fake_agent_project(tmp_path: Path) -> None:
    (tmp_path / "fake_agent.py").write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "from myteam.workflows.results import report_result\n"
        "Path('seen-prompt.txt').write_text(sys.argv[1], encoding='utf-8')\n"
        "report_result({'ok': True})\n"
        "assert sys.stdin.readline() == 'exit\\n'\n",
        encoding="utf-8",
    )
    (tmp_path / "fake_config.py").write_text(
        textwrap.dedent(
            """
            import json
            import sys
            from pathlib import Path

            class MarkdownFakeAgentConfig:
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
                    Path('observed-markdown-agent-settings.json').write_text(
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
                    return 'native-session'

                def get_usage_info(self, session_data):
                    return None
            """
        ).lstrip(),
        encoding="utf-8",
    )
    (tmp_path / ".myteam.yaml").write_text(
        "agents:\n  fake-agent: fake_config.py::MarkdownFakeAgentConfig\n",
        encoding="utf-8",
    )


def test_markdown_workflow_frontmatter_controls_run_agent_settings(run_myteam, tmp_path: Path) -> None:
    write_markdown_fake_agent_project(tmp_path)
    workflow = tmp_path / "workflow.md"
    workflow.write_text(
        "---\n"
        "type: workflow\n"
        "description: exercise frontmatter settings\n"
        "agent: fake-agent\n"
        "model: frontmatter-model\n"
        "reasoning: medium\n"
        "interactive: false\n"
        "session_id: previous-session\n"
        "fork: true\n"
        "extra_args:\n"
        "  - --flag\n"
        "  - value\n"
        "input:\n"
        "  topic: topic to discuss\n"
        "output:\n"
        "  ok: whether the agent completed\n"
        "---\n"
        "Discuss {{ topic }}.\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "start", "workflow.md", "--input", '{"topic": "release"}')

    assert result.exit_code == 0
    assert result.stdout == '{"ok": true}\n'
    assert json.loads((tmp_path / "observed-markdown-agent-settings.json").read_text(encoding="utf-8")) == {
        "model": "frontmatter-model",
        "reasoning": "medium",
        "interactive": False,
        "session_id": "previous-session",
        "fork": True,
        "extra_args": ["--flag", "value"],
    }
    prompt = (tmp_path / "seen-prompt.txt").read_text(encoding="utf-8")
    assert "Discuss release." in prompt
    assert "ok" in prompt
    assert "whether the agent completed" in prompt


def test_markdown_workflow_input_schema_is_advisory_not_enforced(run_myteam, tmp_path: Path) -> None:
    write_markdown_fake_agent_project(tmp_path)
    workflow = tmp_path / "workflow.md"
    workflow.write_text(
        "---\n"
        "type: workflow\n"
        "description: advisory input schema\n"
        "agent: fake-agent\n"
        "input:\n"
        "  expected: caller should supply this, but it is not schema-enforced\n"
        "---\n"
        "Prompt body.\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "start", "workflow.md", "--input", '{"unexpected": "allowed"}')

    assert result.exit_code == 0
    assert result.stdout == '{"ok": true}\n'
