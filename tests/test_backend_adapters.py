from __future__ import annotations

import pytest

from myteam.workflow.agents.backends import (
    BackendAdapter,
    CodexBackendAdapter,
    PTY_RIGHT_ARROW,
    get_backend,
)


def test_codex_backend_builds_initial_argv() -> None:
    backend = CodexBackendAdapter()

    assert backend.build_argv(["codex"], "prompt text") == ["codex", "prompt text"]


def test_codex_backend_builds_resume_argv() -> None:
    backend = CodexBackendAdapter()

    assert backend.build_argv(["codex"], "prompt text", session_id="thread-123") == [
        "codex",
        "resume",
        "thread-123",
        "prompt text",
    ]


def test_codex_backend_encodes_submit_sequence() -> None:
    backend = CodexBackendAdapter()

    assert backend.encode_input("hello\n") == b"hello" + PTY_RIGHT_ARROW + b"\r"
    assert backend.encode_exit() == b"/quit" + PTY_RIGHT_ARROW + b"\r"


def test_get_backend_returns_backend_adapter() -> None:
    backend = get_backend("codex")

    assert isinstance(backend, BackendAdapter)
    assert isinstance(backend, CodexBackendAdapter)
    assert backend.name == "codex"


def test_get_backend_rejects_unknown_backend() -> None:
    with pytest.raises(KeyError, match="Unknown workflow backend: missing"):
        get_backend("missing")
