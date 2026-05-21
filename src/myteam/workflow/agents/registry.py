from __future__ import annotations

from pathlib import Path

from ..models import AgentConfig
from .runtime import AgentSessionContext, resolve_agent_runtime_config


DEFAULT_AGENT = "codex"


def get_agent_config(name: str | None) -> AgentConfig:
    agent_name = DEFAULT_AGENT if name is None else name
    cwd = Path.cwd().resolve()
    runtime_config = resolve_agent_runtime_config(
        agent_name,
        project_root=cwd,
        session_context=AgentSessionContext(
            home=Path.home().resolve(),
            project_root=cwd,
            launch_cwd=cwd,
        ),
    )
    return {
        "name": runtime_config.name,
        "argv": [runtime_config.exec],
    }
