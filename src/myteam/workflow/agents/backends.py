from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

PTY_RIGHT_ARROW = b"\x1b[C"


class BackendAdapter(ABC):
    name: ClassVar[str]
    session_discovery_prompt: ClassVar[str]
    exit_text: ClassVar[str]

    @abstractmethod
    def encode_input(self, text: str) -> bytes:
        raise NotImplementedError

    def encode_exit(self) -> bytes:
        return self.encode_input(self.exit_text)

    @abstractmethod
    def build_argv(
        self,
        agent_argv: list[str],
        prompt_text: str,
        *,
        session_id: str | None = None,
    ) -> list[str]:
        raise NotImplementedError


class CodexBackendAdapter(BackendAdapter):
    name = "codex"
    session_discovery_prompt = (
        "Return your Codex session ID as session_id. "
        "You can find it by running `printenv CODEX_THREAD_ID`."
    )
    exit_text = "/quit"

    def encode_input(self, text: str) -> bytes:
        payload = text.rstrip("\r\n")
        return payload.encode("utf-8") + PTY_RIGHT_ARROW + b"\r"

    def build_argv(
        self,
        agent_argv: list[str],
        prompt_text: str,
        *,
        session_id: str | None = None,
    ) -> list[str]:
        if session_id is None:
            return [*agent_argv, prompt_text]
        return [*agent_argv, "resume", session_id, prompt_text]


class PiBackendAdapter(BackendAdapter):
    name = "pi"
    session_discovery_prompt = "Return your Pi session ID as session_id."
    exit_text = "/quit"

    def encode_input(self, text: str) -> bytes:
        payload = text.rstrip("\r\n")
        return payload.encode("utf-8") + PTY_RIGHT_ARROW + b"\r"

    def build_argv(
        self,
        agent_argv: list[str],
        prompt_text: str,
        *,
        session_id: str | None = None,
    ) -> list[str]:
        if session_id is None:
            return [*agent_argv, prompt_text]
        return [*agent_argv, "resume", session_id, prompt_text]


_BACKENDS: dict[str, BackendAdapter] = {
    "codex": CodexBackendAdapter(),
    "pi": PiBackendAdapter(),
}


def get_backend(name: str) -> BackendAdapter:
    try:
        return _BACKENDS[name]
    except KeyError as exc:
        raise KeyError(f"Unknown workflow backend: {name}") from exc
