from __future__ import annotations

from copy import deepcopy

from .models import AgentConfig

DEFAULT_AGENT = "codex"
DEFAULT_AGENT_CONFIG: AgentConfig = {
    "name": DEFAULT_AGENT,
    "argv": ["codex"],
    "exit_text": "/quit\r",
    "prompt_as_argument": False,
}

_KNOWN_AGENTS: dict[str, AgentConfig] = {
    DEFAULT_AGENT: DEFAULT_AGENT_CONFIG,
}


def get_agent_config(name: str | None) -> AgentConfig:
    agent_name = DEFAULT_AGENT if name is None else name
    try:
        return deepcopy(_KNOWN_AGENTS[agent_name])
    except KeyError as exc:
        raise KeyError(f"Unknown workflow agent: {agent_name}") from exc
