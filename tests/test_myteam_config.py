from __future__ import annotations

from pathlib import Path

import pytest

from myteam.config import load_myteam_config
from myteam.workflows.agents.runtime import AgentSessionContext, resolve_agent_runtime_config


def test_load_myteam_config_parses_defaults_and_agents(tmp_path: Path) -> None:
    config_path = tmp_path / ".myteam.yaml"
    config_path.write_text(
        "defaults:\n"
        "  agent: myagent\n"
        "  model: gpt-5.4-nano\n"
        "  reasoning: medium\n"
        "  interactive: true\n"
        "  session_id: session-123\n"
        "  fork: false\n"
        "  extra_args:\n"
        "    - --foo\n"
        "agents:\n"
        "  myagent: agents/myagent.py::MyAgentConfig\n"
        "  codex-mini: agents/codex_mini.py::CodexMiniConfig\n",
        encoding="utf-8",
    )

    config = load_myteam_config(tmp_path)

    assert config is not None
    assert config.path == config_path
    assert config.defaults.agent == "myagent"
    assert config.defaults.model == "gpt-5.4-nano"
    assert config.defaults.reasoning == "medium"
    assert config.defaults.interactive is True
    assert config.defaults.session_id == "session-123"
    assert config.defaults.fork is False
    assert config.defaults.extra_args == ("--foo",)
    assert config.agents == {
        "myagent": "agents/myagent.py::MyAgentConfig",
        "codex-mini": "agents/codex_mini.py::CodexMiniConfig",
    }


def test_hyphenated_agent_name_can_resolve_from_myteam_yaml(tmp_path: Path) -> None:
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "codex_mini.py").write_text(
        "class CodexMiniConfig:\n"
        "    def build_argv(self, prompt_text, model=None, reasoning=None, interactive=True, session_id=None, fork=False, extra_args=None):\n"
        "        return ['codex-mini', prompt_text]\n"
        "    def get_exit_sequence(self):\n"
        "        return b'/quit\\r'\n"
        "    def locate_session_data(self, nonce, context):\n"
        "        return context.launch_cwd / 'session.jsonl'\n"
        "    def get_session_id(self, session_data):\n"
        "        return 'native-session'\n"
        "    def get_usage_info(self, session_data):\n"
        "        return None\n",
        encoding="utf-8",
    )
    (tmp_path / ".myteam.yaml").write_text(
        "agents:\n"
        "  codex-mini: agents/codex_mini.py::CodexMiniConfig\n",
        encoding="utf-8",
    )

    config = resolve_agent_runtime_config(
        "codex-mini",
        project_root=tmp_path,
        session_context=AgentSessionContext(
            home=tmp_path,
            project_root=tmp_path,
            launch_cwd=tmp_path,
        ),
    )

    assert config.name == "codex-mini"
    assert config.exec == "codex-mini"
    assert config.build_argv("hello") == ["codex-mini", "hello"]


def test_local_agent_config_errors_do_not_fall_back_to_packaged_config(tmp_path: Path) -> None:
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "codex.py").write_text(
        "class CustomCodexConfig:\n"
        "    def build_argv(self, prompt_text, model=None, reasoning=None, interactive=True, session_id=None, fork=False, extra_args=None):\n"
        "        return ['custom-codex', prompt_text]\n"
        "    def get_exit_sequence(self):\n"
        "        return b'/quit\\r'\n"
        "    def locate_session_data(self, nonce, context):\n"
        "        return context.launch_cwd / 'session.jsonl'\n"
        "    def get_session_id(self, session_data):\n"
        "        return 'custom-native-session'\n"
        "    def get_usage_info(self, session_data):\n"
        "        return None\n",
        encoding="utf-8",
    )
    (tmp_path / ".myteam.yaml").write_text(
        "agents:\n"
        "  codex: agents/codex.py::MissingConfig\n",
        encoding="utf-8",
    )

    with pytest.raises(KeyError, match="Invalid local workflow agent config for codex"):
        resolve_agent_runtime_config(
            "codex",
            project_root=tmp_path,
            session_context=AgentSessionContext(
                home=tmp_path,
                project_root=tmp_path,
                launch_cwd=tmp_path,
            ),
        )


def test_builtin_agent_still_resolves_when_unrelated_local_config_exists(tmp_path: Path) -> None:
    (tmp_path / ".myteam.yaml").write_text(
        "agents:\n"
        "  myagent: agents/myagent.py::MyAgentConfig\n",
        encoding="utf-8",
    )

    config = resolve_agent_runtime_config(
        "claude",
        project_root=tmp_path,
        session_context=AgentSessionContext(
            home=tmp_path,
            project_root=tmp_path,
            launch_cwd=tmp_path,
        ),
    )

    assert config.name == "claude"
    assert config.exec == "claude"
