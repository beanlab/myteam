"""myteam framework and CLI for skills, workflows, and agent sessions."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import tomllib

from .commands import onboard
from .explain import explain_resources
from .listing import list_resources
from .skills import load_skill
from .workflows import SessionResult, UsageInfo, report_workflow_result, run_agent

__all__ = [
    "__version__",
    "explain_resources",
    "list_resources",
    "load_skill",
    "onboard",
    "run_agent",
    "report_workflow_result",
    "SessionResult",
    "UsageInfo",
]


def _project_version() -> str:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if pyproject.exists():
        with pyproject.open("rb") as handle:
            project = tomllib.load(handle)["project"]
        return str(project["version"])

    try:
        return version("myteam")
    except PackageNotFoundError:
        raise RuntimeError("Unable to determine myteam version") from None


__version__ = _project_version()
