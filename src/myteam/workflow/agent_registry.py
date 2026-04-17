from __future__ import annotations

from .models import AgentConfig

DEFAULT_AGENT = "codex"

_KNOWN_AGENTS = {
    DEFAULT_AGENT: AgentConfig(name=DEFAULT_AGENT, argv=["codex"], exit_text="/quit\n"),
}


def get_agent_config(name: str | None) -> AgentConfig:
    agent_name = DEFAULT_AGENT if name is None else name
    try:
        return _KNOWN_AGENTS[agent_name]
    except KeyError as exc:
        raise KeyError(f"Unknown workflow agent: {agent_name}") from exc
