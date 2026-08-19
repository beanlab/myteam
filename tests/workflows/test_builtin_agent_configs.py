from __future__ import annotations

import os
from pathlib import Path

import pytest

from myteam.workflows.agents.claude import build_argv as build_claude_argv
from myteam.workflows.agents.claude import get_session_info as get_claude_session_info
from myteam.workflows.agents.claude import get_usage_info as get_claude_usage_info
from myteam.workflows.agents.claude import _project_session_dir_name as claude_project_session_dir_name
from myteam.workflows.agents.codex import get_usage_info as get_codex_usage_info
from myteam.workflows.agents.pi import get_usage_info as get_pi_usage_info
from myteam.workflows.agents.runtime import AgentSessionContext, resolve_agent_runtime_config


def agent_session_context(home: Path, launch_cwd: Path | None = None) -> AgentSessionContext:
    return AgentSessionContext(
        home=home.resolve(),
        project_root=(launch_cwd or home).resolve(),
        launch_cwd=(launch_cwd or home).resolve(),
    )


def test_codex_get_usage_info_attributes_cumulative_deltas_by_model(tmp_path: Path) -> None:
    session_path = tmp_path / "rollout-session.jsonl"
    session_path.write_text(
        '{"type":"turn_context","payload":{"model":"gpt-5.4"}}\n'
        '{"type":"event_msg","payload":{"type":"token_count","info":{"total_token_usage":{"input_tokens":100,"cached_input_tokens":20,"output_tokens":10,"reasoning_output_tokens":2,"total_tokens":110}}}}\n'
        '{"type":"event_msg","payload":{"type":"token_count","info":{"total_token_usage":{"input_tokens":250,"cached_input_tokens":70,"output_tokens":30,"reasoning_output_tokens":5,"total_tokens":280}}}}\n'
        '{"type":"turn_context","payload":{"model":"gpt-5-mini"}}\n'
        '{"type":"event_msg","payload":{"type":"token_count","info":{"total_token_usage":{"input_tokens":300,"cached_input_tokens":80,"output_tokens":50,"reasoning_output_tokens":9,"total_tokens":350}}}}\n',
        encoding="utf-8",
    )

    usage = get_codex_usage_info(session_path)

    assert usage is not None
    usage_by_model = {item.model: item for item in usage}
    assert set(usage_by_model) == {"gpt-5.4", "gpt-5-mini"}
    assert usage_by_model["gpt-5.4"].input_tokens == 250
    assert usage_by_model["gpt-5.4"].cached_input_tokens == 70
    assert usage_by_model["gpt-5.4"].output_tokens == 30
    assert usage_by_model["gpt-5.4"].reasoning_output_tokens == 5
    assert usage_by_model["gpt-5.4"].total_tokens == 280
    assert usage_by_model["gpt-5-mini"].input_tokens == 50
    assert usage_by_model["gpt-5-mini"].cached_input_tokens == 10
    assert usage_by_model["gpt-5-mini"].output_tokens == 20
    assert usage_by_model["gpt-5-mini"].reasoning_output_tokens == 4
    assert usage_by_model["gpt-5-mini"].total_tokens == 70


def test_pi_get_usage_info_aggregates_every_response_by_model(tmp_path: Path) -> None:
    session_path = tmp_path / "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"
    session_path.write_text(
        '{"type":"assistant","message":{"model":"gpt-5.6-sol","usage":{"input":10,"cacheRead":20,"cacheWrite":30,"output":4,"reasoning":2,"totalTokens":64,"cost":{"total":0.1}}}}\n'
        '{"type":"assistant","message":{"model":"gpt-5.6-sol","usage":{"input":5,"cacheRead":40,"cacheWrite":6,"output":7,"reasoning":3,"totalTokens":58,"cost":{"total":0.2}}}}\n'
        '{"type":"assistant","message":{"model":"other-model","usage":{"input":1,"cacheRead":2,"cacheWrite":3,"output":4,"reasoning":1,"totalTokens":10,"cost":{"total":0.05}}}}\n',
        encoding="utf-8",
    )

    usage = get_pi_usage_info(session_path)

    assert usage is not None
    usage_by_model = {item.model: item for item in usage}
    assert set(usage_by_model) == {"gpt-5.6-sol", "other-model"}
    assert usage_by_model["gpt-5.6-sol"].input_tokens == 111
    assert usage_by_model["gpt-5.6-sol"].cached_input_tokens == 60
    assert usage_by_model["gpt-5.6-sol"].output_tokens == 11
    assert usage_by_model["gpt-5.6-sol"].reasoning_output_tokens == 5
    assert usage_by_model["gpt-5.6-sol"].total_tokens == 122
    assert usage_by_model["gpt-5.6-sol"].estimated_cost == pytest.approx(0.3)
    assert usage_by_model["other-model"].total_tokens == 10
    assert usage_by_model["other-model"].estimated_cost == pytest.approx(0.05)


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
