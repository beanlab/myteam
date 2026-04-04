"""Helpers for executing role and skill loaders."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from myteam.utils import PROJECT_ROOT_ENV_VAR


def run_loader(
    load_py: Path,
    *,
    cwd: Path,
    project_root: Path | None = None,
    capture_output: bool,
) -> subprocess.CompletedProcess[str]:
    env = None
    if project_root is not None:
        env = dict(os.environ)
        env[PROJECT_ROOT_ENV_VAR] = str(project_root)

    return subprocess.run(
        [sys.executable, str(load_py)],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=capture_output,
        check=False,
    )


def capture_loader_output(
    load_py: Path,
    *,
    cwd: Path,
    project_root: Path | None = None,
) -> str:
    result = run_loader(load_py, cwd=cwd, project_root=project_root, capture_output=True)
    if result.returncode != 0:
        stderr = result.stderr.strip() or f"loader exited with status {result.returncode}"
        raise RuntimeError(stderr)
    return result.stdout
