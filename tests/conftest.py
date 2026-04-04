from __future__ import annotations

import io
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from myteam.cli import main as cli_main


@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str


@pytest.fixture
def run_myteam(monkeypatch):
    def runner(
        project_dir: Path,
        *args: str,
        input_text: str | None = None,
        env_overrides: dict[str, str] | None = None,
    ) -> CommandResult:
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = str(SRC) if not existing_pythonpath else f"{SRC}{os.pathsep}{existing_pythonpath}"
        if env_overrides:
            env.update(env_overrides)

        completed = subprocess.run(
            [sys.executable, "-m", "myteam", *args],
            cwd=project_dir,
            env=env,
            text=True,
            capture_output=True,
            input=input_text,
            check=False,
        )

        return CommandResult(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    return runner


@pytest.fixture
def run_myteam_inprocess(monkeypatch):
    def runner(
        project_dir: Path,
        *args: str,
        input_text: str | None = None,
        env_overrides: dict[str, str] | None = None,
    ) -> CommandResult:
        stdout = io.StringIO()
        stderr = io.StringIO()
        monkeypatch.chdir(project_dir)
        monkeypatch.setattr(sys, "argv", ["myteam", *args])
        if input_text is not None:
            monkeypatch.setattr(sys, "stdin", io.StringIO(input_text))
        if env_overrides:
            for key, value in env_overrides.items():
                monkeypatch.setenv(key, value)

        exit_code = 0
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                cli_main()
            except SystemExit as exc:
                code = exc.code
                if code is None:
                    exit_code = 0
                elif isinstance(code, int):
                    exit_code = code
                else:
                    exit_code = 1

        return CommandResult(
            exit_code=exit_code,
            stdout=stdout.getvalue(),
            stderr=stderr.getvalue(),
        )

    return runner


@pytest.fixture
def initialized_project(tmp_path: Path, run_myteam) -> Path:
    result = run_myteam(tmp_path, "init")
    assert result.exit_code == 0, result.stderr
    return tmp_path
