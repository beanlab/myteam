import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

PTY_RIGHT_ARROW = b"\x1b[C"

def encode_input(text: str) -> bytes:
    payload = text.rstrip("\r\n")
    return payload.encode("utf-8") + PTY_RIGHT_ARROW + b"\r"

def iter_jsonl_reverse(path: Path, block_size: int = 1024 * 1024) -> Iterator[dict[str, Any]]:
    with path.open("rb") as f:
        f.seek(0, 2)
        pos = f.tell()
        buffer = bytearray()

        while pos > 0:
            read_size = min(block_size, pos)
            pos -= read_size
            f.seek(pos)

            buffer[:0] = f.read(read_size)

            lines = buffer.split(b"\n")
            buffer = lines.pop(0)

            for line in reversed(lines):
                obj = _decode_json_object(line)
                if obj is None:
                    continue
                if isinstance(obj, dict):
                    yield obj

        if buffer:
            obj = _decode_json_object(buffer)
            if isinstance(obj, dict):
                yield obj


def _decode_json_object(data: bytes) -> Any | None:
    text = data.decode("utf-8", errors="ignore").strip()
    if not text:
        return None

    candidates = [text]
    if not text.startswith("{") and not text.startswith("["):
        candidates.append(f"{{{text}}}")

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None

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
