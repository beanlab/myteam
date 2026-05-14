from __future__ import annotations

from ..models import AgentConfig
from .runtime import resolve_agent_runtime_config


DEFAULT_AGENT = "codex"


def get_agent_config(name: str | None) -> AgentConfig:
    agent_name = DEFAULT_AGENT if name is None else name
    runtime_config = resolve_agent_runtime_config(agent_name)
    return {
        "name": runtime_config.name,
        "argv": [runtime_config.exec],
    }
