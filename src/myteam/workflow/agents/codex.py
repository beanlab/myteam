from __future__ import annotations

import re
from pathlib import Path

EXEC = "codex"
SESSION_ID_RE = re.compile(r"rollout-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-([0-9a-f-]{36})\.jsonl$")
EXIT_COMMAND = "/quit"


def build_argv(prompt_text: str, session_id: str | None = None) -> list[str]:
    if session_id is None:
        return [EXEC, prompt_text]
    return [EXEC, "resume", session_id, prompt_text]


def get_session_id(nonce: str) -> str:
    sessions_dir = Path.home() / ".codex" / "sessions"
    candidates = sorted(
        sessions_dir.rglob("rollout-*.jsonl"),
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

    raise LookupError(f"No Codex session found for nonce: {nonce}")


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0
