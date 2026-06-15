from __future__ import annotations

from pathlib import Path

import pytest

from myteam.config import load_myteam_config
from myteam.workflows.agents.runtime import AgentSessionContext, resolve_agent_runtime_config


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
