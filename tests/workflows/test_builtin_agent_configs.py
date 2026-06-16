from __future__ import annotations

import os
from pathlib import Path

import pytest

from myteam.workflows.agents.claude import build_argv as build_claude_argv
from myteam.workflows.agents.claude import get_session_info as get_claude_session_info
from myteam.workflows.agents.claude import get_usage_info as get_claude_usage_info
from myteam.workflows.agents.claude import _project_session_dir_name as claude_project_session_dir_name
from myteam.workflows.agents.runtime import AgentSessionContext, resolve_agent_runtime_config


def agent_session_context(home: Path, launch_cwd: Path | None = None) -> AgentSessionContext:
    return AgentSessionContext(
        home=home.resolve(),
        project_root=(launch_cwd or home).resolve(),
        launch_cwd=(launch_cwd or home).resolve(),
    )


def test_packaged_claude_config_resolves(tmp_path: Path) -> None:
    config = resolve_agent_runtime_config(
        "claude",
        project_root=tmp_path,
        session_context=agent_session_context(tmp_path),
    )

    assert config.name == "claude"
    assert config.exec == "claude"
    assert config.build_argv("prompt") == ["claude", "prompt"]


def test_claude_build_argv_supports_session_modes_and_settings() -> None:
    assert build_claude_argv("prompt") == ["claude", "prompt"]
    assert build_claude_argv("prompt", False) == ["claude", "--print", "prompt"]
    assert build_claude_argv("prompt", True, "resume-session", False) == [
        "claude",
        "--resume",
        "resume-session",
        "prompt",
    ]
    assert build_claude_argv("prompt", True, "fork-session", True) == [
        "claude",
        "--resume",
        "fork-session",
        "--fork-session",
        "prompt",
    ]
    assert build_claude_argv("prompt", False, "resume-session", False) == [
        "claude",
        "--print",
        "--resume",
        "resume-session",
        "prompt",
    ]
    assert build_claude_argv(
        "prompt",
        False,
        "fork-session",
        True,
        "sonnet",
        ("--permission-mode", "auto"),
        "high",
    ) == [
        "claude",
        "--print",
        "--resume",
        "fork-session",
        "--fork-session",
        "--model",
        "sonnet",
        "--effort",
        "high",
        "--permission-mode",
        "auto",
        "prompt",
    ]


def test_claude_get_session_info_finds_newest_matching_project_session(tmp_path: Path) -> None:
    project_dir = tmp_path / "workspace" / "project"
    project_dir.mkdir(parents=True)
    sessions_dir = tmp_path / ".claude" / "projects" / claude_project_session_dir_name(project_dir)
    sessions_dir.mkdir(parents=True)
    older_match = sessions_dir / "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"
    newest_nonmatch = sessions_dir / "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb.jsonl"
    newest_match = sessions_dir / "cccccccc-cccc-cccc-cccc-cccccccccccc.jsonl"
    older_match.write_text("nonce-123", encoding="utf-8")
    newest_nonmatch.write_text("other", encoding="utf-8")
    newest_match.write_text("nonce-123", encoding="utf-8")
    os.utime(older_match, (1, 1))
    os.utime(newest_nonmatch, (2, 2))
    os.utime(newest_match, (3, 3))

    assert get_claude_session_info("nonce-123", agent_session_context(tmp_path, project_dir)) == (
        "cccccccc-cccc-cccc-cccc-cccccccccccc",
        newest_match,
    )


def test_claude_get_session_info_prefers_project_dir_over_newer_unrelated_match(tmp_path: Path) -> None:
    project_dir = tmp_path / "workspace" / "project"
    project_dir.mkdir(parents=True)
    sessions_root = tmp_path / ".claude" / "projects"
    project_sessions_dir = sessions_root / claude_project_session_dir_name(project_dir)
    unrelated_sessions_dir = sessions_root / "-tmp-other-project"
    project_sessions_dir.mkdir(parents=True)
    unrelated_sessions_dir.mkdir(parents=True)
    project_match = project_sessions_dir / "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"
    newer_unrelated_match = unrelated_sessions_dir / "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb.jsonl"
    project_match.write_text("nonce-123", encoding="utf-8")
    newer_unrelated_match.write_text("nonce-123", encoding="utf-8")
    os.utime(project_match, (1, 1))
    os.utime(newer_unrelated_match, (2, 2))

    assert get_claude_session_info("nonce-123", agent_session_context(tmp_path, project_dir)) == (
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        project_match,
    )


def test_claude_get_session_info_honors_claude_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_dir = tmp_path / "custom-claude"
    project_dir = tmp_path / "workspace" / "project"
    project_dir.mkdir(parents=True)
    sessions_dir = config_dir / "projects" / claude_project_session_dir_name(project_dir)
    sessions_dir.mkdir(parents=True)
    match = sessions_dir / "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"
    match.write_text("nonce-123", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))

    assert get_claude_session_info("nonce-123", agent_session_context(tmp_path, project_dir)) == (
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        match,
    )


def test_claude_get_usage_info_extracts_tokens_and_estimates_cost(tmp_path: Path) -> None:
    session_path = tmp_path / "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"
    session_path.write_text(
        '{"type":"user","message":{"content":"nonce-123"},"sessionId":"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}\n'
        '{"type":"assistant","message":{"model":"claude-sonnet-4-6","usage":{"input_tokens":100,"cache_creation_input_tokens":50,"cache_read_input_tokens":20,"output_tokens":10}}}\n',
        encoding="utf-8",
    )

    usage = get_claude_usage_info(session_path)

    assert usage is not None
    assert usage.model == "claude-sonnet-4-6"
    assert usage.input_tokens == 170
    assert usage.cached_input_tokens == 20
    assert usage.output_tokens == 10
    assert usage.total_tokens == 180
    assert usage.estimated_cost == pytest.approx(0.000606)


def test_claude_get_usage_info_returns_none_without_usage(tmp_path: Path) -> None:
    session_path = tmp_path / "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"
    session_path.write_text('{"message":{"model":"claude-sonnet-4-6"}}\n', encoding="utf-8")

    assert get_claude_usage_info(session_path) is None
