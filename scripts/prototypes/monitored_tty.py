from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from myteam.workflow.tty_wrapper import run_pty_session


def _dog_monitor():
    seen = bytearray()
    injected = False

    def on_output(chunk: bytes) -> str | None:
        nonlocal injected
        if injected:
            return None

        seen.extend(chunk.lower())
        if b"dog" in seen:
            injected = True
            return "/quit\n"
        return None

    return on_output


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/prototypes/monitored_tty.py <command> [args...]", file=sys.stderr)
        raise SystemExit(2)

    result = run_pty_session(sys.argv[1:], None, _dog_monitor())
    raise SystemExit(result.exit_code)
