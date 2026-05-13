from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


PTY_RIGHT_ARROW = b"\x1b[C"


@dataclass(frozen=True)
class BackendAdapter:
    name: str
    submit_text: Callable[[str], bytes]
    session_discovery_prompt: str
    exit_text: str = "/quit"

    def encode_exit(self) -> bytes:
        return self.submit_text(self.exit_text)

    def build_argv(
        self,
        agent_argv: list[str],
        prompt_text: str,
        *,
        session_id: str | None = None,
    ) -> list[str]:
        if session_id is None:
            return [*agent_argv, prompt_text]
        if self.name == "codex":
            return [*agent_argv, "resume", session_id, prompt_text]
        return [*agent_argv, "resume", session_id, prompt_text]


def _encode_codex_submit(text: str) -> bytes:
    payload = text.rstrip("\r\n")
    return payload.encode("utf-8") + PTY_RIGHT_ARROW + b"\r"


_BACKENDS = {
    "codex": BackendAdapter(
        name="codex",
        submit_text=_encode_codex_submit,
        session_discovery_prompt=(
            "Return your Codex session ID as session_id. "
            "You can find it by running `printenv CODEX_THREAD_ID`."
        ),
    ),
    "pi": BackendAdapter(
        name="pi",
        submit_text=_encode_codex_submit,
        session_discovery_prompt="Return your Pi session ID as session_id.",
    ),
}


def get_backend(name: str) -> BackendAdapter:
    try:
        return _BACKENDS[name]
    except KeyError as exc:
        raise KeyError(f"Unknown workflow backend: {name}") from exc
