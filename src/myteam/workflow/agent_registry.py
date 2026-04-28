from __future__ import annotations

from copy import deepcopy

from .models import AgentConfig

DEFAULT_AGENT = "codex"
DEFAULT_AGENT_CONFIG: AgentConfig = {
    "name": DEFAULT_AGENT,
    "argv": ["codex"],
    "exit_text": "/quit\n",
    # Live PTY probing shows Codex emits banner and setup output before the
    # composer is actually interactive. The first stable input-ready frame is
    # the one that has restored the cursor and exited synchronized-update mode.
    "initial_input_readiness_markers": [b"\x1b[?25h", b"\x1b[?2026l"],
    "initial_input_quiet_period_seconds": 0.15,
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
