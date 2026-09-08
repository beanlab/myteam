from __future__ import annotations

import json
from pathlib import Path
import textwrap

import pytest

from myteam.workflows.execution.protocol import ENV_SOCKET


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
                    session_name=None,
                ):
                    Path('observed-markdown-agent-settings.json').write_text(
                        json.dumps(
                            {
                                'session_name': session_name,
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


def test_markdown_workflow_frontmatter_controls_run_agent_settings(
    run_myteam, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv(ENV_SOCKET, raising=False)
    write_markdown_fake_agent_project(tmp_path)
    workflow = tmp_path / "workflow.md"
    workflow.write_text(
        "---\n"
        "type: workflow\n"
        "description: exercise frontmatter settings\n"
        "agent: fake-agent\n"
        "session_name: Markdown contract\n"
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
    assert result.stdout.endswith('{"ok": true}\n')
    assert "Session started" not in result.stderr
    assert "Session ended" not in result.stderr
    assert json.loads((tmp_path / "observed-markdown-agent-settings.json").read_text(encoding="utf-8")) == {
        "session_name": "Markdown contract",
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


def test_markdown_workflow_cli_overrides_all_agent_settings(run_myteam, tmp_path: Path) -> None:
    write_markdown_fake_agent_project(tmp_path)
    (tmp_path / "workflow.md").write_text(
        "---\n"
        "type: workflow\n"
        "description: exercise CLI settings\n"
        "agent: unavailable-agent\n"
        "session_name: frontmatter name\n"
        "model: frontmatter-model\n"
        "reasoning: low\n"
        "interactive: true\n"
        "fork: false\n"
        "---\n"
        "Discuss {{ topic }}.\n",
        encoding="utf-8",
    )

    result = run_myteam(
        tmp_path,
        "start",
        "workflow.md",
        "--input",
        '{"topic": "release"}',
        "--agent=fake-agent",
        "--session-name",
        "first name",
        "--session_name=CLI review",
        "--model",
        "first-model",
        "--model=gpt-5",
        "--reasoning",
        "high",
        "--interactive=false",
        "--extra-args",
        "[--first]",
        "--extra_args=[--flag, value]",
        "--session-id",
        "old-session",
        "--session_id=session-42",
        "--fork=true",
    )

    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout == '{"ok": true}\n'
    assert json.loads((tmp_path / "observed-markdown-agent-settings.json").read_text(encoding="utf-8")) == {
        "session_name": "CLI review",
        "model": "gpt-5",
        "reasoning": "high",
        "interactive": False,
        "session_id": "session-42",
        "fork": True,
        "extra_args": ["--flag", "value"],
    }
    assert "Discuss release." in (tmp_path / "seen-prompt.txt").read_text(encoding="utf-8")


def test_markdown_workflow_cli_null_falls_through_to_effective_default(
    run_myteam, tmp_path: Path
) -> None:
    write_markdown_fake_agent_project(tmp_path)
    (tmp_path / ".myteam.yaml").write_text(
        (tmp_path / ".myteam.yaml").read_text(encoding="utf-8")
        + "defaults:\n  model: configured-model\n",
        encoding="utf-8",
    )
    (tmp_path / "workflow.md").write_text(
        "---\n"
        "type: workflow\n"
        "description: precedence\n"
        "agent: fake-agent\n"
        "model: frontmatter-model\n"
        "---\nPrompt.\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "start", "workflow.md", "--model", "null")

    assert result.exit_code == 0
    settings = json.loads(
        (tmp_path / "observed-markdown-agent-settings.json").read_text(encoding="utf-8")
    )
    assert settings["model"] == "configured-model"
    assert settings["session_name"] == "workflow.md"


@pytest.mark.parametrize(
    ("trailing_args", "diagnostic"),
    [
        (("--unknown", "value"), "unknown"),
        (("positional",), "positional"),
        (("--model",), "model"),
        (("--model=",), "model"),
        (("--extra-args", "[unterminated"), "extra-args"),
        (("--interactive", "quoted-string"), "interactive"),
        (("--fork", "true"), "session_id"),
    ],
)
def test_markdown_workflow_rejects_invalid_trailing_settings_before_agent_launch(
    run_myteam,
    tmp_path: Path,
    trailing_args: tuple[str, ...],
    diagnostic: str,
) -> None:
    write_markdown_fake_agent_project(tmp_path)
    (tmp_path / "workflow.md").write_text(
        "---\ntype: workflow\ndescription: invalid settings\nagent: fake-agent\n---\nPrompt.\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "start", "workflow.md", *trailing_args)

    assert result.exit_code != 0
    assert diagnostic.lower() in result.stdout.lower()
    assert "traceback" not in result.stderr.lower()
    assert not (tmp_path / "observed-markdown-agent-settings.json").exists()


@pytest.mark.parametrize(
    ("invalid_setting", "diagnostic"),
    [("interactive: not-a-boolean", "interactive"), ("fork: true", "session_id")],
)
def test_markdown_workflow_rejects_invalid_effective_frontmatter_before_launch(
    run_myteam, tmp_path: Path, invalid_setting: str, diagnostic: str
) -> None:
    write_markdown_fake_agent_project(tmp_path)
    (tmp_path / "workflow.md").write_text(
        "---\ntype: workflow\ndescription: invalid frontmatter\nagent: fake-agent\n"
        f"{invalid_setting}\n---\nPrompt.\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "start", "workflow.md")

    assert result.exit_code != 0
    assert diagnostic.lower() in result.stdout.lower()
    assert "traceback" not in result.stderr.lower()
    assert not (tmp_path / "observed-markdown-agent-settings.json").exists()


def test_markdown_workflow_reports_invalid_config_through_result_channel(
    run_myteam, tmp_path: Path
) -> None:
    write_markdown_fake_agent_project(tmp_path)
    (tmp_path / ".myteam.yaml").write_text("defaults:\n  interactive: not-a-boolean\n", encoding="utf-8")
    (tmp_path / "workflow.md").write_text(
        "---\ntype: workflow\ndescription: invalid config\nagent: fake-agent\n---\nPrompt.\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "start", "workflow.md")

    assert result.exit_code != 0
    assert "interactive" in result.stdout.lower()
    assert "traceback" not in result.stderr.lower()
    assert not (tmp_path / "observed-markdown-agent-settings.json").exists()


@pytest.mark.parametrize("session_id_source", ["frontmatter", "default", "cli"])
def test_markdown_workflow_allows_fork_with_effective_session_id(
    run_myteam, tmp_path: Path, session_id_source: str
) -> None:
    write_markdown_fake_agent_project(tmp_path)
    if session_id_source == "default":
        (tmp_path / ".myteam.yaml").write_text(
            (tmp_path / ".myteam.yaml").read_text(encoding="utf-8")
            + "defaults:\n  session_id: configured-session\n",
            encoding="utf-8",
        )
    frontmatter_id = "session_id: frontmatter-session\n" if session_id_source == "frontmatter" else ""
    (tmp_path / "workflow.md").write_text(
        "---\ntype: workflow\ndescription: fork\nagent: fake-agent\n"
        f"{frontmatter_id}---\nPrompt.\n",
        encoding="utf-8",
    )
    args = ("--fork", "true")
    if session_id_source == "cli":
        args += ("--session-id", "cli-session")

    result = run_myteam(tmp_path, "start", "workflow.md", *args)

    assert result.exit_code == 0
    settings = json.loads(
        (tmp_path / "observed-markdown-agent-settings.json").read_text(encoding="utf-8")
    )
    assert settings["fork"] is True
    assert settings["session_id"] == {
        "frontmatter": "frontmatter-session",
        "default": "configured-session",
        "cli": "cli-session",
    }[session_id_source]


def test_markdown_workflow_allows_explicit_fork_false_without_session_id(
    run_myteam, tmp_path: Path
) -> None:
    write_markdown_fake_agent_project(tmp_path)
    (tmp_path / "workflow.md").write_text(
        "---\ntype: workflow\ndescription: no fork\nagent: fake-agent\n---\nPrompt.\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "start", "workflow.md", "--fork", "false")

    assert result.exit_code == 0
    settings = json.loads(
        (tmp_path / "observed-markdown-agent-settings.json").read_text(encoding="utf-8")
    )
    assert settings["fork"] is False
    assert settings["session_id"] is None


def test_markdown_workflow_help_short_circuits_wrapper_processing(run_myteam, tmp_path: Path) -> None:
    write_markdown_fake_agent_project(tmp_path)
    (tmp_path / ".myteam.yaml").write_text("defaults: [invalid\n", encoding="utf-8")
    (tmp_path / "workflow.md").write_text(
        "---\ntype: workflow\ndescription: help\ninteractive: invalid\n---\nPrompt.\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "start", "workflow.md", "--input", "[]", "--help")

    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout.startswith("Usage: myteam start <markdown-workflow>")
    for option in (
        "--agent",
        "--session-name",
        "--session_name",
        "--model",
        "--reasoning",
        "--interactive",
        "--extra-args",
        "--extra_args",
        "--session-id",
        "--session_id",
        "--fork",
        "--input",
        "--help",
    ):
        assert option in result.stdout
    assert "yaml" in result.stdout.lower()
    assert "last" in result.stdout.lower()
    assert "frontmatter" in result.stdout.lower()
    assert "default" in result.stdout.lower()
    assert not (tmp_path / "observed-markdown-agent-settings.json").exists()


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
