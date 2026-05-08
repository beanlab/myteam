from __future__ import annotations

from copy import deepcopy

from ..models import AgentConfig


DEFAULT_AGENT = "codex"

_KNOWN_AGENTS: dict[str, AgentConfig] = {
    DEFAULT_AGENT: {
        "name": DEFAULT_AGENT,
        "argv": ["codex"],
        "backend": "codex",
    }
}


def get_agent_config(name: str | None) -> AgentConfig:
    agent_name = DEFAULT_AGENT if name is None else name
    try:
        return deepcopy(_KNOWN_AGENTS[agent_name])
    except KeyError as exc:
        raise KeyError(f"Unknown workflow agent: {agent_name}") from exc
