from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import TypedDict, Literal

from ..frontmatter import split_markdown_frontmatter, parse_python_frontmatter
from ..templates import get_template
from ..templates import get_template_file


class AgentSettings(TypedDict):
    agent: str
    model: str
    interactive: bool
    extra_args: tuple[str, ...]
    session_id: str
    fork: bool


class MarkdownWorkflowInfo(AgentSettings):
    type: Literal['markdown']
    input: dict
    """Schema describing input shape"""
    prompt: str
    output: dict
    """Schema describing output shape"""


class PythonWorkflowInfo(TypedDict):
    type: Literal['python']
    input: dict
    output: dict


WorkflowInfo = MarkdownWorkflowInfo | PythonWorkflowInfo


def new_workflow(workflow_name: str):
    pass  # TODO - same logic as new skill


def resolve_agent_settings(explicit_settings: AgentSettings, defaults: WorkflowDefaults) -> AgentSettings:
    return AgentSettings(
        **{
            field: explicit_settings.get(field, getattr(defaults, field))
            for field in AgentSettings.__annotations__.keys()
        }
    )


def _start_markdown_workflow(workflow_file: Path, workflow_input_json: str):
    # TODO - common way to run subpython scripts?
    workflow_defaults = Path('.myteam.yaml')
    result = subprocess.run(
        [
            sys.executable,
            get_template_file('workflow_markdown_wrapper.py'),
            str(workflow_file),
            workflow_input_json,
            str(workflow_defaults.absolute())
        ],
        cwd=workflow_file.parent,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
    )
    # TODO - do something with stderr?
    return result.stdout


def _start_python_workflow(workflow_file: Path, workflow_input_json: str):
    args = [sys.executable, str(workflow_file)]
    if workflow_input_json:
        args.extend(["--input", workflow_input_json])
    result = subprocess.run(
        args,
        cwd=workflow_file.parent,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return result.stdout


def start_workflow(workflow_name: str | None = None, *args: str, workflow_input_json: str | None = None):
    """Start a workflow invocation under the prototype mothership supervisor."""
    from ..proto import start

    return start(workflow_name, *args, workflow_input_json=workflow_input_json)


def run_agent(**kwargs):
    """Start an agent session through the active prototype mothership supervisor."""
    from ..proto import run_agent as proto_run_agent

    return proto_run_agent(**kwargs)
