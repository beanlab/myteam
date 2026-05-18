from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=None)
def resolve_session_path(
    nonce: str,
    search_roots: tuple[Path, ...],
    pattern: str,
) -> Path:
    for root in search_roots:
        if not root.exists():
            continue
        try:
            candidates = sorted(root.rglob(pattern), key=_mtime, reverse=True)
        except OSError:
            continue
        for path in candidates:
            try:
                if nonce in path.read_text(encoding="utf-8", errors="ignore"):
                    return path
            except OSError:
                continue
    raise LookupError(f"No session file found for nonce: {nonce}")


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0
