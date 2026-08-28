from __future__ import annotations

from pathlib import Path

import pytest

import myteam.config as config_module
from myteam.config import load_myteam_config
from myteam.workflows.agents.runtime import (
    AgentSessionContext,
    resolve_agent_runtime_config,
)


def write_config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / ".myteam.yaml"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("config_text", "message"),
    [
        ("[not a mapping]\n", "must be a YAML mapping"),
        ("defaults: nope\n", "defaults .* must be a mapping"),
        ("agents: nope\n", "agents .* must be a mapping"),
        ("agents:\n  '': target.py::Config\n", "non-empty string names"),
        ("agents:\n  custom: ''\n", "must be a non-empty string target"),
        ("defaults:\n  interactive: sometimes\n", "defaults .* are invalid"),
        ("defaults:\n  unexpected: value\n", "defaults .* are invalid"),
    ],
)
def test_load_myteam_config_rejects_invalid_documented_shapes(
    tmp_path: Path,
    config_text: str,
    message: str,
) -> None:
    write_config(tmp_path, config_text)

    with pytest.raises(ValueError, match=message):
        load_myteam_config(tmp_path)


def test_load_myteam_config_rejects_malformed_yaml(tmp_path: Path) -> None:
    write_config(tmp_path, "defaults: [unterminated\n")

    with pytest.raises(ValueError, match="Failed to parse myteam config"):
        load_myteam_config(tmp_path)


def test_load_myteam_config_returns_none_without_global_or_project_file(
    tmp_path: Path,
) -> None:
    assert load_myteam_config(tmp_path) is None


def test_load_myteam_config_uses_global_file(
    tmp_path: Path,
    isolated_home: Path,
) -> None:
    write_config(
        isolated_home,
        "defaults:\n"
        "  agent: home-agent\n"
        "  session_name: Home session\n"
        "  model: home-model\n"
        "  reasoning: medium\n"
        "  interactive: false\n"
        "  session_id: home-session-id\n"
        "  fork: true\n"
        "  extra_args: [--home]\n"
        "  usage_logging: summary\n"
        "  timeout: 30\n"
        "agents:\n  home-agent: adapters/home.py::HomeConfig\n",
    )

    config = load_myteam_config(tmp_path)

    assert config is not None
    assert config.defaults.model_dump() == {
        "agent": "home-agent",
        "session_name": "Home session",
        "model": "home-model",
        "reasoning": "medium",
        "interactive": False,
        "session_id": "home-session-id",
        "fork": True,
        "extra_args": ("--home",),
        "usage_logging": "summary",
        "timeout": 30,
    }
    assert config.agents == {"home-agent": "adapters/home.py::HomeConfig"}


def test_load_myteam_config_merges_global_and_project_by_documented_precedence(
    tmp_path: Path,
    isolated_home: Path,
) -> None:
    write_config(
        isolated_home,
        "defaults:\n"
        "  agent: global-agent\n"
        "  session_name: Global session\n"
        "  model: global-model\n"
        "  reasoning: high\n"
        "  extra_args: [--global, value]\n"
        "agents:\n"
        "  global-agent: global.py::GlobalConfig\n"
        "  shared: global-shared.py::GlobalSharedConfig\n",
    )
    write_config(
        tmp_path,
        "defaults:\n"
        "  session_name: null\n"
        "  model: project-model\n"
        "  extra_args: [--project]\n"
        "agents:\n"
        "  project-agent: project.py::ProjectConfig\n"
        "  shared: project-shared.py::ProjectSharedConfig\n",
    )

    config = load_myteam_config(tmp_path)

    assert config is not None
    assert config.defaults.agent == "global-agent"  # omission inherits
    assert config.defaults.session_name is None  # explicit null clears
    assert config.defaults.model == "project-model"
    assert config.defaults.reasoning == "high"
    assert config.defaults.extra_args == ("--project",)  # whole-field replacement
    assert config.agents == {
        "global-agent": "global.py::GlobalConfig",
        "project-agent": "project.py::ProjectConfig",
        "shared": "project-shared.py::ProjectSharedConfig",
    }


@pytest.mark.parametrize(
    ("bad_source", "bad_text"),
    [
        ("global", "defaults: [unterminated\n"),
        ("global", "defaults:\n  interactive: sometimes\n"),
        ("project", "defaults: [unterminated\n"),
        ("project", "agents:\n  broken: ''\n"),
    ],
)
def test_load_myteam_config_rejects_each_invalid_participating_file_and_names_it(
    tmp_path: Path,
    isolated_home: Path,
    bad_source: str,
    bad_text: str,
) -> None:
    global_path = write_config(isolated_home, "defaults:\n  model: valid-global\n")
    project_path = write_config(tmp_path, "defaults:\n  model: valid-project\n")
    bad_path = global_path if bad_source == "global" else project_path
    bad_path.write_text(bad_text, encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        load_myteam_config(tmp_path)

    assert str(bad_path) in str(exc_info.value)


def test_same_physical_global_and_project_file_is_parsed_once(
    tmp_path: Path,
    isolated_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    global_path = write_config(isolated_home, "defaults:\n  model: shared-model\n")
    (tmp_path / ".myteam.yaml").symlink_to(global_path)
    safe_load_calls = 0
    original_safe_load = config_module.yaml.safe_load

    def count_safe_load(text: str):
        nonlocal safe_load_calls
        safe_load_calls += 1
        return original_safe_load(text)

    monkeypatch.setattr(config_module.yaml, "safe_load", count_safe_load)

    config = load_myteam_config(tmp_path)

    assert config is not None
    assert config.defaults.model == "shared-model"
    assert safe_load_calls == 1


def test_custom_agent_can_override_builtin_name_from_myteam_yaml(tmp_path: Path) -> None:
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "codex.py").write_text(
        "class CustomCodexConfig:\n"
        "    EXEC = 'custom-codex'\n"
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
    write_config(tmp_path, "agents:\n  codex: agents/codex.py::CustomCodexConfig\n")

    config = resolve_agent_runtime_config(
        "codex",
        project_root=tmp_path,
        session_context=AgentSessionContext(
            home=tmp_path,
            project_root=tmp_path,
            launch_cwd=tmp_path,
        ),
    )

    assert config.name == "codex"
    assert config.exec == "custom-codex"
    assert config.build_argv("hello") == ["custom-codex", "hello"]
