import os
import subprocess
import sys
from pathlib import Path
from typing import TypedDict, Literal

from .config import WorkflowDefaults, load_workflow_defaults
from ..frontmatter import split_markdown_frontmatter, parse_python_frontmatter
from ..prefix import resolve_prefix, relative_to_myteam
from ..templates import get_template
from ..prefix import get_myteam_root, resolve_target
from ..templates import get_template_file


class AgentSettings(TypedDict):
    agent: str
    model: str
    extra_args: tuple[str, ...]
    interactive: bool
    session_id: str
    fork: bool


class MarkdownWorkflowInfo(AgentSettings):
    type: Literal['markdown']
    name: str
    """Name by which this workflow is identified"""
    description: str
    input: dict
    """Schema describing input shape"""
    prompt: str
    output: dict
    """Schema describing output shape"""


class PythonWorkflowInfo(AgentSettings):
    type: Literal['python']
    name: str
    description: str
    input: dict
    output: dict


WorkflowInfo = MarkdownWorkflowInfo | PythonWorkflowInfo


def new_workflow(workflow_name: str):
    workflow_path = Path(workflow_name)
    if workflow_path.exists():
        raise RuntimeError(f"Task '{workflow_name}' already exists")
    if workflow_path.suffix == ".md":
        resolve_prefix(workflow_name).write_text(get_template('new_workflow.md'))
    if workflow_path.suffix == ".py" or not workflow_path.suffix:
        resolve_prefix(workflow_name).write_text(get_template('new_workflow.py'))
    raise NotImplementedError(f"Workflow type '{workflow_path.suffix}' not supported")


def explain_workflows() -> str:
    return get_template('explain_workflows.md')


def resolve_agent_settings(explicit_settings: AgentSettings, defaults: WorkflowDefaults) -> AgentSettings:
    return AgentSettings(
        **{
            field: explicit_settings.get(field, getattr(defaults, field))
            for field in AgentSettings.__annotations__.keys()
        }
    )


def _parse_markdown_workflow_info(
        workflow_name: str, frontmatter: dict, content: str,
        defaults: WorkflowDefaults
) -> WorkflowInfo:
    # noinspection PyTypeChecker
    # frontmatter is AgentSettings + a few fields
    return MarkdownWorkflowInfo(
        type='markdown',
        name=workflow_name,
        description=frontmatter.pop('description'),
        input=frontmatter.pop('input'),
        prompt=content,
        output=frontmatter.pop('output'),
        **resolve_agent_settings(frontmatter, defaults)
    )


def _parse_python_workflow_info(
        workflow_name: str, frontmatter: dict, defaults: WorkflowDefaults
) -> WorkflowInfo:
    # noinspection PyTypeChecker
    # frontmatter is AgentSettings + a few fields
    return PythonWorkflowInfo(
        type='python',
        name=workflow_name,
        description=frontmatter.pop('description'),
        input=frontmatter.pop('input'),
        output=frontmatter.pop('output'),
        **resolve_agent_settings(frontmatter, defaults)
    )


def get_workflows(prefix: str) -> str:
    """List the workflow headers for all workflows under `prefix`"""
    workflow_defaults = load_workflow_defaults(get_myteam_root())

    workflow_infos = []
    for file in resolve_prefix(prefix).glob('*'):
        if file.is_dir():
            continue

        if file.suffix == '.md':
            frontmatter, content = split_markdown_frontmatter(file.read_text())
            if frontmatter.get('type') == 'workflow':
                workflow_name = relative_to_myteam(file)
                info = _parse_markdown_workflow_info(workflow_name, frontmatter, content, workflow_defaults)
                workflow_infos.append(info)

        elif file.suffix == '.py':
            frontmatter = parse_python_frontmatter(file.read_text())
            if frontmatter.get('type') == 'workflow':
                workflow_name = relative_to_myteam(file)
                info = _parse_python_workflow_info(workflow_name, frontmatter)
                workflow_infos.append(info)
        else:
            continue

    return workflow_infos


def _start_markdown_workflow(workflow_file: Path, workflow_input_json: str):
    # TODO - common way to run subpython scripts?
    result = subprocess.run(
        [
            sys.executable,
            get_template_file('workflow_markdown_wrapper.py'),
            str(workflow_file),
            workflow_input_json
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
        args.extend(["--json", workflow_input_json])
    result = subprocess.run(
        args,
        cwd=workflow_file.parent,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
    )
    return result.stdout


def start_workflow(workflow_name: str, workflow_input_json: str | None = None):
    # if env var is set, it's a child workflow
    # if it's part of a regular agent session, is_cli will be false
    is_cli = (sys.stdin.isatty() or sys.stdout.isatty() or sys.stderr.isatty())
    if not os.environ.get("SESSION_NONCE") and not is_cli:
        raise RuntimeError("Workflows may only be started from the CLI or from another workflow.")

    workflow_file = resolve_target(workflow_name)

    if workflow_file.suffix == '.md':
        _start_markdown_workflow(workflow_file, workflow_input_json)

    elif workflow_file.suffix == '.py':
        _start_python_workflow(workflow_file, workflow_input_json)

    else:
        raise NotImplementedError(workflow_file.suffix)
