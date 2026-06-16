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


@pytest.fixture
def run_myteam(monkeypatch):
    def runner(project_dir: Path, *args: str) -> CommandResult:
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = str(SRC) if not existing_pythonpath else f"{SRC}{os.pathsep}{existing_pythonpath}"

        completed = subprocess.run(
            [sys.executable, "-m", "myteam", *args],
            cwd=project_dir,
            env=env,
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

