from __future__ import annotations

from pathlib import Path
import sys
import textwrap

import pytest

from myteam.workflow.tty_wrapper import run_pty_session


def _write_agent_script(tmp_path: Path) -> Path:
    script = tmp_path / "test_agent.py"
    script.write_text(
        textwrap.dedent(
            """
            import sys

            print("READY", flush=True)

            for line in sys.stdin:
                text = line.rstrip("\\n")
                print(f"INPUT:{text}", flush=True)
                if text == "hello":
                    print("OBJECTIVE_COMPLETE", flush=True)
                if text == "/quit":
                    print("EXITING", flush=True)
                    print("TRAILING", flush=True)
                    break
            """
        ),
        encoding="utf-8",
    )
    return script


def test_run_pty_session_captures_output_and_writes_callback_responses(tmp_path: Path):
    script = _write_agent_script(tmp_path)
    seen_chunks: list[bytes] = []

    def on_output(chunk: bytes) -> str | None:
        seen_chunks.append(chunk)
        if b"OBJECTIVE_COMPLETE" in b"".join(seen_chunks):
            return "/quit\n"
        return None

    result = run_pty_session(
        [sys.executable, str(script)],
        "hello\n",
        on_output,
        inactivity_timeout_seconds=5,
        graceful_shutdown_timeout_seconds=5,
    )

    assert result.exit_code == 0
    assert "READY" in result.transcript
    assert "INPUT:hello" in result.transcript
    assert "OBJECTIVE_COMPLETE" in result.transcript
    assert "INPUT:/quit" in result.transcript
    assert "EXITING" in result.transcript
    assert "TRAILING" in result.transcript


def test_run_pty_session_raises_on_inactivity_timeout(tmp_path: Path):
    script = tmp_path / "silent_agent.py"
    script.write_text(
        textwrap.dedent(
            """
            import time

            time.sleep(2)
            """
        ),
        encoding="utf-8",
    )

    with pytest.raises(TimeoutError, match="inactivity timeout"):
        run_pty_session(
            [sys.executable, str(script)],
            None,
            lambda chunk: None,
            inactivity_timeout_seconds=1,
            graceful_shutdown_timeout_seconds=1,
        )
