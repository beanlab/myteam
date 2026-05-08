from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


PTY_RIGHT_ARROW = b"\x1b[C"


@dataclass(frozen=True)
class BackendAdapter:
    name: str
    submit_text: Callable[[str], bytes]
    exit_text: str = "/quit"

    def encode_input(self, text: str) -> bytes:
        return self.submit_text(text)

    def encode_exit(self) -> bytes:
        return self.submit_text(self.exit_text)


def _encode_codex_submit(text: str) -> bytes:
    payload = text.rstrip("\r\n")
    return payload.encode("utf-8") + PTY_RIGHT_ARROW + b"\r"


_BACKENDS = {
    "codex": BackendAdapter(name="codex", submit_text=_encode_codex_submit),
    "pi": BackendAdapter(name="pi", submit_text=_encode_codex_submit),
}


def get_backend(name: str) -> BackendAdapter:
    try:
        return _BACKENDS[name]
    except KeyError as exc:
        raise KeyError(f"Unknown workflow backend: {name}") from exc
