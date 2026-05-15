from __future__ import annotations

import re
from pathlib import Path

EXEC = "pi"
SESSION_ID_RE = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$")
EXIT_COMMAND = "/quit"


def build_argv(
    prompt_text: str,
    interactive: bool = True,
    resume_session_id: str | None = None,
    fork_session_id: str | None = None,
) -> list[str]:
    argv = [EXEC]
    if not interactive:
        argv.append("--print")
    if resume_session_id is not None:
        argv.extend(["--session", resume_session_id])
    if fork_session_id is not None:
        argv.extend(["--fork", fork_session_id])
    argv.append(prompt_text)
    return argv


def get_session_id(nonce: str) -> str:
    sessions_dir = Path.home() / ".pi" / "agent" / "sessions"
    project_sessions_dir = sessions_dir / _project_session_dir_name(Path.cwd())
    candidates = _session_candidates(project_sessions_dir)
    if project_sessions_dir != sessions_dir:
        candidates.extend(path for path in _session_candidates(sessions_dir) if path not in candidates)

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


def _project_session_dir_name(path: Path) -> str:
    project_path = path.resolve().as_posix().strip("/")
    return f"--{project_path.replace('/', '-')}--"


def _session_candidates(sessions_dir: Path) -> list[Path]:
    try:
        return sorted(
            sessions_dir.rglob("*.jsonl"),
            key=_mtime,
            reverse=True,
        )
    except OSError:
        return []


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0
