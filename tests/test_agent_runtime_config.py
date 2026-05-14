from __future__ import annotations

import os
from pathlib import Path

import pytest

from myteam.workflow.agents.codex import get_session_id
from myteam.workflow.agents.runtime import resolve_agent_runtime_config
from myteam.workflow.parser import load_workflow


def test_resolve_uses_packaged_default_without_creating_project_config(tmp_path: Path, monkeypatch):
    logs: list[str] = []
    monkeypatch.chdir(tmp_path)

    config = resolve_agent_runtime_config("codex", logger=logs.append)

    assert config.name == "codex"
    assert config.exec == "codex"
    assert not (tmp_path / ".myteam" / ".config").exists()
    assert any("not found" in line for line in logs)
    assert any("packaged workflow agent config" in line for line in logs)


def test_resolve_uses_valid_local_override(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / ".myteam" / ".config"
    config_dir.mkdir(parents=True)
    (config_dir / "custom.py").write_text(
        "EXEC = 'custom-agent'\n"
        "EXIT_SEQUENCE = b'exit\\n'\n"
        "def encode_input(text):\n"
        "    return text.encode('utf-8')\n"
        "def get_session_id(nonce):\n"
        "    return 'local-session'\n",
        encoding="utf-8",
    )

    config = resolve_agent_runtime_config("custom")

    assert config.name == "custom"
    assert config.exec == "custom-agent"
    assert config.build_argv("prompt") == ["custom-agent", "prompt"]
    assert config.get_session_id("nonce") == "local-session"


def test_resolve_falls_back_when_local_override_is_invalid(tmp_path: Path, monkeypatch):
    logs: list[str] = []
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / ".myteam" / ".config"
    config_dir.mkdir(parents=True)
    (config_dir / "codex.py").write_text("EXEC = 'broken'\n", encoding="utf-8")

    config = resolve_agent_runtime_config("codex", logger=logs.append)

    assert config.name == "codex"
    assert config.exec == "codex"
    assert any("unusable" in line for line in logs)
    assert any("packaged workflow agent config" in line for line in logs)


def test_resolve_rejects_unknown_agent(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(KeyError, match="Unknown workflow agent: missing"):
        resolve_agent_runtime_config("missing")


def test_load_workflow_accepts_project_local_agent(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / ".myteam" / ".config"
    config_dir.mkdir(parents=True)
    (config_dir / "custom.py").write_text(
        "EXEC = 'custom-agent'\n"
        "EXIT_SEQUENCE = b'exit\\n'\n"
        "def encode_input(text):\n"
        "    return text.encode('utf-8')\n"
        "def get_session_id(nonce):\n"
        "    return 'local-session'\n",
        encoding="utf-8",
    )
    workflow_file = tmp_path / "workflow.yaml"
    workflow_file.write_text(
        "step1:\n"
        "  agent: custom\n"
        "  prompt: hello\n"
        "  output:\n"
        "    message: hi\n",
        encoding="utf-8",
    )

    workflow = load_workflow(workflow_file)

    assert workflow["step1"]["agent"] == "custom"


def test_codex_get_session_id_finds_newest_matching_rollout(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    sessions_dir = tmp_path / ".codex" / "sessions" / "2026" / "05" / "14"
    sessions_dir.mkdir(parents=True)
    older_match = sessions_dir / "rollout-2026-05-14T10-00-00-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"
    newest_nonmatch = sessions_dir / "rollout-2026-05-14T10-01-00-bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb.jsonl"
    newest_match = sessions_dir / "rollout-2026-05-14T10-02-00-cccccccc-cccc-cccc-cccc-cccccccccccc.jsonl"
    older_match.write_text("nonce-123", encoding="utf-8")
    newest_nonmatch.write_text("other", encoding="utf-8")
    newest_match.write_text("nonce-123", encoding="utf-8")
    os.utime(older_match, (1, 1))
    os.utime(newest_nonmatch, (2, 2))
    os.utime(newest_match, (3, 3))

    assert get_session_id("nonce-123") == "cccccccc-cccc-cccc-cccc-cccccccccccc"
