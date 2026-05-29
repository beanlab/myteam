from __future__ import annotations

from pathlib import Path

from myteam.workflow.resolution.session_resolution import resolve_session_id


class _DummyAgentConfig:
    def __init__(self, session_id: str, session_path: Path) -> None:
        self._session_id = session_id
        self._session_path = session_path

    def get_session_info(self, nonce: str):
        return self._session_id, self._session_path


def test_resolve_session_id_accepts_missing_payload(tmp_path: Path):
    agent_config = _DummyAgentConfig("session-123", tmp_path / "session")

    result = resolve_session_id(
        payload=None,
        session_id=None,
        fork=False,
        nonce="nonce-abc",
        agent_config=agent_config,
    )

    assert result == ("session-123", tmp_path / "session")
