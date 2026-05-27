from __future__ import annotations

import json
import tempfile
from pathlib import Path
from threading import Lock
from typing import Any


_REGISTRY_DIR = Path(tempfile.gettempdir()) / "myteam-workflow-sessions"
_REGISTRY_LOCK = Lock()


def load_channel_details(nonce: str, kind: str) -> tuple[str, str]:
    path = _registry_path(nonce)
    if not path.exists():
        raise ValueError(f"No workflow session found for nonce: {nonce}")

    data = _read_registry(path)
    if data.get("nonce") != nonce:
        raise ValueError(f"No workflow session found for nonce: {nonce}")

    channel = data.get(kind)
    if not isinstance(channel, dict):
        raise ValueError(f"No {kind} channel found for nonce: {nonce}")

    socket_path = channel.get("socket")
    token = channel.get("token")
    if not isinstance(socket_path, str) or not socket_path:
        raise ValueError(f"No {kind} channel found for nonce: {nonce}")
    if not isinstance(token, str) or not token:
        raise ValueError(f"No {kind} channel found for nonce: {nonce}")
    return socket_path, token


def register_channel(nonce: str, kind: str, *, socket_path: str, token: str) -> None:
    with _REGISTRY_LOCK:
        _ensure_registry_dir()
        path = _registry_path(nonce)
        data = _read_registry(path) if path.exists() else {"version": 1, "nonce": nonce}
        if data.get("nonce") != nonce:
            data = {"version": 1, "nonce": nonce}

        data[kind] = {
            "socket": socket_path,
            "token": token,
        }
        _write_registry(path, data)


def unregister_channel(nonce: str, kind: str) -> None:
    with _REGISTRY_LOCK:
        path = _registry_path(nonce)
        if not path.exists():
            return

        data = _read_registry(path)
        if data.get("nonce") != nonce:
            return

        data.pop(kind, None)
        if "control" not in data and "result" not in data:
            try:
                path.unlink()
            except OSError:
                pass
            return

        _write_registry(path, data)


def _registry_path(nonce: str) -> Path:
    return _REGISTRY_DIR / f"{nonce}.json"


def _ensure_registry_dir() -> None:
    _REGISTRY_DIR.mkdir(parents=True, exist_ok=True)


def _read_registry(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_registry(path: Path, data: dict[str, Any]) -> None:
    _ensure_registry_dir()
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data), encoding="utf-8")
    tmp_path.replace(path)
