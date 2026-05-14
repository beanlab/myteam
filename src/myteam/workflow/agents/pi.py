from __future__ import annotations

import re
from pathlib import Path

EXEC = "pi"

PTY_RIGHT_ARROW = b"\x1b[C"
SESSION_ID_RE = re.compile(r".+_([0-9a-f-]{36})\.jsonl$")


def encode_input(text: str) -> bytes:
    payload = text.rstrip("\r\n")
    return payload.encode("utf-8") + PTY_RIGHT_ARROW + b"\r"


EXIT_SEQUENCE = encode_input("/quit")


def build_argv(prompt_text: str, session_id: str | None = None) -> list[str]:
    if session_id is None:
        return [EXEC, prompt_text]
    return [EXEC, "--session", session_id, prompt_text]


def get_session_id(nonce: str) -> str:
    sessions_dir = Path.home() / ".pi" / "agent" / "sessions"
    candidates = sorted(
        sessions_dir.rglob("*.jsonl"),
        key=_mtime,
        reverse=True,
    )

    for path in candidates:
        try:
            if nonce not in path.read_text(encoding="utf-8", errors="ignore"):
                continue
        except OSError:
            continue

        match = SESSION_ID_RE.search(path.name)
        if match:
            return match.group(1)

    raise LookupError(f"No Pi session found for nonce: {nonce}")


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0
