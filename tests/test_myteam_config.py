from __future__ import annotations

import json
from pathlib import Path

import pytest

from myteam.config import load_myteam_config, load_workflow_defaults
from myteam.workflows.agents.runtime import (
    AgentSessionContext,
    resolve_agent_runtime_config,
)


def test_load_myteam_config_parses_defaults_and_agents(tmp_path: Path) -> None:
    config_path = tmp_path / ".myteam.yaml"
    config_path.write_text(
        "defaults:\n"
        "  agent: myagent\n"
        "  session_name: 1234\n"
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
    assert not hasattr(config, "path")
    assert config.defaults.agent == "myagent"
    assert config.defaults.session_name == "1234"
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


@pytest.mark.parametrize("session_name", ["two\nlines", "carriage\rreturn"])
def test_load_myteam_config_rejects_session_name_newlines(tmp_path: Path, session_name: str) -> None:
    (tmp_path / ".myteam.yaml").write_text(
        "defaults:\n  session_name: " + json.dumps(session_name) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="newline"):
        load_myteam_config(tmp_path)


def write_agent_config(path: Path, class_name: str, executable: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"class {class_name}:\n"
        f"    EXEC = {executable!r}\n"
        "    def build_argv(self, prompt_text, **kwargs):\n"
        "        return [self.EXEC, prompt_text]\n"
        "    def get_exit_sequence(self):\n"
        "        return b'exit\\n'\n"
        "    def locate_session_data(self, nonce, context):\n"
        "        return context.launch_cwd / 'session.jsonl'\n"
        "    def get_session_id(self, session_data):\n"
        "        return 'session-id'\n"
        "    def get_usage_info(self, session_data):\n"
        "        return None\n",
        encoding="utf-8",
    )


def test_merged_agents_resolve_relative_to_the_file_that_defined_each_agent(
    tmp_path: Path,
    isolated_home: Path,
) -> None:
    write_agent_config(isolated_home / "agents" / "global.py", "GlobalConfig", "from-global")
    write_agent_config(tmp_path / "agents" / "project.py", "ProjectConfig", "from-project")
    (isolated_home / ".myteam.yaml").write_text(
        "agents:\n"
        "  global-agent: agents/global.py::GlobalConfig\n"
        "  shared: agents/global.py::GlobalConfig\n",
        encoding="utf-8",
    )
    (tmp_path / ".myteam.yaml").write_text(
        "agents:\n"
        "  project-agent: agents/project.py::ProjectConfig\n"
        "  shared: agents/project.py::ProjectConfig\n",
        encoding="utf-8",
    )
    context = AgentSessionContext(
        home=isolated_home,
        project_root=tmp_path,
        launch_cwd=tmp_path,
    )

    global_config = resolve_agent_runtime_config(
        "global-agent", project_root=tmp_path, session_context=context
    )
    project_config = resolve_agent_runtime_config(
        "project-agent", project_root=tmp_path, session_context=context
    )
    overridden_config = resolve_agent_runtime_config(
        "shared", project_root=tmp_path, session_context=context
    )

    assert global_config.exec == "from-global"
    assert project_config.exec == "from-project"
    assert overridden_config.exec == "from-project"


def test_global_config_does_not_bypass_legacy_project_defaults(
    tmp_path: Path,
    isolated_home: Path,
) -> None:
    (isolated_home / ".myteam.yaml").write_text(
        "defaults:\n  model: global-model\n",
        encoding="utf-8",
    )
    myteam_folder = tmp_path / ".myteam"
    myteam_folder.mkdir()
    (myteam_folder / ".config.yaml").write_text(
        "model: legacy-project-model\n",
        encoding="utf-8",
    )

    defaults = load_workflow_defaults(myteam_folder)

    assert defaults is not None
    assert defaults.model == "legacy-project-model"


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
