from __future__ import annotations

import os
from pathlib import Path

import pytest

from myteam.workflow.agents.codex import build_argv as build_codex_argv
from myteam.workflow.agents.codex import get_session_id as get_codex_session_id
from myteam.workflow.agents.pi import build_argv as build_pi_argv
from myteam.workflow.agents.pi import get_session_id as get_pi_session_id
from myteam.workflow.agents.runtime import AgentSessionContext
from myteam.workflow.agents.runtime import resolve_agent_runtime_config
from myteam.workflow.parser import load_workflow


def agent_session_context(
    tmp_path: Path,
    *,
    project_root: Path | None = None,
    launch_cwd: Path | None = None,
) -> AgentSessionContext:
    root = tmp_path if project_root is None else project_root
    cwd = root if launch_cwd is None else launch_cwd
    return AgentSessionContext(
        home=tmp_path,
        project_root=root,
        launch_cwd=cwd,
    )


def test_resolve_uses_packaged_default_without_creating_project_config(tmp_path: Path, monkeypatch):
    logs: list[str] = []
    monkeypatch.chdir(tmp_path)

    config = resolve_agent_runtime_config(
        "codex",
        project_root=tmp_path,
        session_context=agent_session_context(tmp_path),
        logger=logs.append,
    )

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
        "EXIT_COMMAND = 'exit'\n"
        "def get_session_id(nonce, context):\n"
        "    return f'{nonce}:{context.project_root.name}:{context.launch_cwd.name}'\n"
        "def build_argv(prompt_text, interactive=True, resume_session_id=None, fork_session_id=None, extra_args=None):\n"
        "    return ['custom-agent', prompt_text]\n",
        encoding="utf-8",
    )

    config = resolve_agent_runtime_config(
        "custom",
        project_root=tmp_path,
        session_context=agent_session_context(tmp_path),
    )

    assert config.name == "custom"
    assert config.exec == "custom-agent"
    assert config.exit_sequence == b"exit\x1b[C\r"
    assert config.build_argv("prompt") == ["custom-agent", "prompt"]
    assert config.get_session_id("nonce") == f"nonce:{tmp_path.name}:{tmp_path.name}"


def test_resolve_rejects_local_override_without_build_argv(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / ".myteam" / ".config"
    config_dir.mkdir(parents=True)
    (config_dir / "custom.py").write_text(
        "EXEC = 'custom-agent'\n"
        "EXIT_COMMAND = 'exit'\n"
        "def get_session_id(nonce, context):\n"
        "    return 'local-session'\n",
        encoding="utf-8",
    )

    with pytest.raises(KeyError, match="missing build_argv"):
        resolve_agent_runtime_config(
            "custom",
            project_root=tmp_path,
            session_context=agent_session_context(tmp_path),
        )


def test_resolve_rejects_local_get_session_id_without_context(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / ".myteam" / ".config"
    config_dir.mkdir(parents=True)
    (config_dir / "custom.py").write_text(
        "EXEC = 'custom-agent'\n"
        "EXIT_COMMAND = 'exit'\n"
        "def get_session_id(nonce):\n"
        "    return 'local-session'\n"
        "def build_argv(prompt_text, interactive=True, resume_session_id=None, fork_session_id=None, extra_args=None):\n"
        "    return ['custom-agent', prompt_text]\n",
        encoding="utf-8",
    )

    with pytest.raises(KeyError, match="get_session_id must accept nonce and context"):
        resolve_agent_runtime_config(
            "custom",
            project_root=tmp_path,
            session_context=agent_session_context(tmp_path),
        )


def test_resolve_accepts_legacy_local_exit_sequence(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / ".myteam" / ".config"
    config_dir.mkdir(parents=True)
    (config_dir / "custom.py").write_text(
        "EXEC = 'custom-agent'\n"
        "EXIT_SEQUENCE = b'exit\\n'\n"
        "def get_session_id(nonce, context):\n"
        "    return 'local-session'\n"
        "def build_argv(prompt_text, interactive=True, resume_session_id=None, fork_session_id=None, extra_args=None):\n"
        "    return ['custom-agent', prompt_text]\n",
        encoding="utf-8",
    )

    config = resolve_agent_runtime_config(
        "custom",
        project_root=tmp_path,
        session_context=agent_session_context(tmp_path),
    )

    assert config.exit_sequence == b"exit\n"


def test_resolve_prefers_legacy_exit_sequence_over_exit_command(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / ".myteam" / ".config"
    config_dir.mkdir(parents=True)
    (config_dir / "custom.py").write_text(
        "EXEC = 'custom-agent'\n"
        "EXIT_COMMAND = 'exit-command'\n"
        "EXIT_SEQUENCE = b'exit-sequence\\n'\n"
        "def get_session_id(nonce, context):\n"
        "    return 'local-session'\n"
        "def build_argv(prompt_text, interactive=True, resume_session_id=None, fork_session_id=None, extra_args=None):\n"
        "    return ['custom-agent', prompt_text]\n",
        encoding="utf-8",
    )

    config = resolve_agent_runtime_config(
        "custom",
        project_root=tmp_path,
        session_context=agent_session_context(tmp_path),
    )

    assert config.exit_sequence == b"exit-sequence\n"


def test_resolve_falls_back_when_local_override_is_invalid(tmp_path: Path, monkeypatch):
    logs: list[str] = []
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / ".myteam" / ".config"
    config_dir.mkdir(parents=True)
    (config_dir / "codex.py").write_text("EXEC = 'broken'\n", encoding="utf-8")

    config = resolve_agent_runtime_config(
        "codex",
        project_root=tmp_path,
        session_context=agent_session_context(tmp_path),
        logger=logs.append,
    )

    assert config.name == "codex"
    assert config.exec == "codex"
    assert any("unusable" in line for line in logs)
    assert any("packaged workflow agent config" in line for line in logs)


def test_resolve_rejects_unknown_agent(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(KeyError, match="Unknown workflow agent: missing"):
        resolve_agent_runtime_config(
            "missing",
            project_root=tmp_path,
            session_context=agent_session_context(tmp_path),
        )


def test_load_workflow_accepts_project_local_agent(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / ".myteam" / ".config"
    config_dir.mkdir(parents=True)
    (config_dir / "custom.py").write_text(
        "EXEC = 'custom-agent'\n"
        "EXIT_COMMAND = 'exit'\n"
        "def get_session_id(nonce, context):\n"
        "    return 'local-session'\n"
        "def build_argv(prompt_text, interactive=True, resume_session_id=None, fork_session_id=None, extra_args=None):\n"
        "    return ['custom-agent', prompt_text]\n",
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


def test_codex_build_argv_supports_session_modes():
    assert build_codex_argv("prompt") == ["codex", "prompt"]
    assert build_codex_argv("prompt", False) == ["codex", "exec", "prompt"]
    assert build_codex_argv("prompt", True, "resume-session", None) == [
        "codex",
        "resume",
        "resume-session",
        "prompt",
    ]
    assert build_codex_argv("prompt", True, None, "fork-session") == [
        "codex",
        "fork",
        "fork-session",
        "prompt",
    ]
    assert build_codex_argv("prompt", False, "resume-session", None) == [
        "codex",
        "exec",
        "resume",
        "resume-session",
        "prompt",
    ]
    assert build_codex_argv("prompt", True, None, None, ["--search"]) == [
        "codex",
        "--search",
        "prompt",
    ]
    assert build_codex_argv("prompt", False, None, None, ["--sandbox", "workspace-write"]) == [
        "codex",
        "exec",
        "--sandbox",
        "workspace-write",
        "prompt",
    ]
    assert build_codex_argv("prompt", True, "resume-session", None, ["--search"]) == [
        "codex",
        "resume",
        "resume-session",
        "--search",
        "prompt",
    ]
    assert build_codex_argv("prompt", True, None, "fork-session", ["--search"]) == [
        "codex",
        "fork",
        "fork-session",
        "--search",
        "prompt",
    ]


def test_codex_build_argv_rejects_noninteractive_fork():
    with pytest.raises(ValueError, match="non-interactive workflow steps do not support"):
        build_codex_argv("prompt", False, None, "fork-session")


def test_pi_build_argv_supports_session_modes():
    assert build_pi_argv("prompt") == ["pi", "prompt"]
    assert build_pi_argv("prompt", False) == ["pi", "--print", "prompt"]
    assert build_pi_argv("prompt", True, "resume-session", None) == [
        "pi",
        "--session",
        "resume-session",
        "prompt",
    ]
    assert build_pi_argv("prompt", True, None, "fork-session") == [
        "pi",
        "--fork",
        "fork-session",
        "prompt",
    ]
    assert build_pi_argv("prompt", False, "resume-session", None) == [
        "pi",
        "--print",
        "--session",
        "resume-session",
        "prompt",
    ]
    assert build_pi_argv("prompt", False, None, "fork-session") == [
        "pi",
        "--print",
        "--fork",
        "fork-session",
        "prompt",
    ]
    assert build_pi_argv("prompt", True, None, None, ["--model", "opus"]) == [
        "pi",
        "--model",
        "opus",
        "prompt",
    ]
    assert build_pi_argv("prompt", False, "resume-session", None, ["--model", "opus"]) == [
        "pi",
        "--print",
        "--session",
        "resume-session",
        "--model",
        "opus",
        "prompt",
    ]
    assert build_pi_argv("prompt", True, None, "fork-session", ["--model", "opus"]) == [
        "pi",
        "--fork",
        "fork-session",
        "--model",
        "opus",
        "prompt",
    ]


def test_codex_get_session_id_finds_newest_matching_rollout(tmp_path: Path):
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

    assert get_codex_session_id("nonce-123", agent_session_context(tmp_path)) == (
        "cccccccc-cccc-cccc-cccc-cccccccccccc"
    )


def test_pi_get_session_id_finds_newest_matching_session(tmp_path: Path):
    project_dir = tmp_path / "workspace" / "project"
    project_dir.mkdir(parents=True)
    project_slug = project_dir.resolve().as_posix().strip("/").replace("/", "-")
    sessions_dir = tmp_path / ".pi" / "agent" / "sessions" / f"--{project_slug}--"
    sessions_dir.mkdir(parents=True)
    older_match = sessions_dir / "2026-05-14T10-00-00-000Z_aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"
    newest_nonmatch = sessions_dir / "2026-05-14T10-01-00-000Z_bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb.jsonl"
    newest_match = sessions_dir / "2026-05-14T10-02-00-000Z_cccccccc-cccc-cccc-cccc-cccccccccccc.jsonl"
    older_match.write_text("nonce-123", encoding="utf-8")
    newest_nonmatch.write_text("other", encoding="utf-8")
    newest_match.write_text("nonce-123", encoding="utf-8")
    os.utime(older_match, (1, 1))
    os.utime(newest_nonmatch, (2, 2))
    os.utime(newest_match, (3, 3))

    assert get_pi_session_id("nonce-123", agent_session_context(tmp_path, launch_cwd=project_dir)) == (
        "cccccccc-cccc-cccc-cccc-cccccccccccc"
    )


def test_pi_get_session_id_prefers_injected_launch_cwd_session_dir(tmp_path: Path):
    project_dir = tmp_path / "workspace" / "project"
    project_dir.mkdir(parents=True)

    sessions_root = tmp_path / ".pi" / "agent" / "sessions"
    project_slug = project_dir.resolve().as_posix().strip("/").replace("/", "-")
    project_sessions_dir = sessions_root / f"--{project_slug}--"
    unrelated_sessions_dir = sessions_root / "--tmp-other-project--"
    project_sessions_dir.mkdir(parents=True)
    unrelated_sessions_dir.mkdir(parents=True)

    project_match = project_sessions_dir / "2026-05-14T19-22-36-232Z_aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"
    newer_unrelated_match = unrelated_sessions_dir / "2026-05-14T19-23-36-232Z_bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb.jsonl"
    project_match.write_text("nonce-123", encoding="utf-8")
    newer_unrelated_match.write_text("nonce-123", encoding="utf-8")
    os.utime(project_match, (1, 1))
    os.utime(newer_unrelated_match, (2, 2))

    assert get_pi_session_id("nonce-123", agent_session_context(tmp_path, launch_cwd=project_dir)) == (
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    )
