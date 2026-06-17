from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str


def _test_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("MYTEAM_AGENT_SESSION_RESULT_SOCKET", None)
    env.pop("MYTEAM_AGENT_SESSION_NONCE", None)
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC) if not existing_pythonpath else f"{SRC}{os.pathsep}{existing_pythonpath}"
    return env


@pytest.fixture
def run_myteam(monkeypatch):
    def runner(project_dir: Path, *args: str) -> CommandResult:
        completed = subprocess.run(
            [sys.executable, "-m", "myteam", *args],
            cwd=project_dir,
            env=_test_env(),
            text=True,
            capture_output=True,
            check=False,
        )

        return CommandResult(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    return runner

