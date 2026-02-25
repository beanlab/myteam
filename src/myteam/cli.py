"""Command-line interface for the myteam package."""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from .download import download, list_available_items
from .constants import ENCODING, AGENTS_DIRNAME, DEFAULT_ROLE, APP_NAME, INFO_FILE, INSTRUCTIONS_FILE, AGENT_PY_FILE, AGENTS_MD_FILE

import fire

from . import __version__


def _base() -> Path:
    return Path.cwd()


def _write_file(path: Path, content: str):
    path.write_text(content, encoding=ENCODING)


def _main_agent_script() -> str:
    """Load the embedded agent template from package data."""
    return resources.files(__package__).joinpath("templates/main_agent_template.py").read_text(encoding=ENCODING)


def _main_instructions_template() -> str:
    """Load the default main-role instructions template."""
    return resources.files(__package__).joinpath("templates/main_instructions_template.md").read_text(encoding=ENCODING)


def _role_agent_script() -> str:
    """Load the generic role agent template."""
    return resources.files(__package__).joinpath("templates/role_agent_template.py").read_text(encoding=ENCODING)


def _agents_md_template() -> str:
    return resources.files(__package__).joinpath("templates/agents_md_template.md").read_text(encoding=ENCODING)


def _agents_root(base: Path = Path.cwd()) -> Path:
    return base / AGENTS_DIRNAME


def _role_dir(role: str) -> Path:
    return _agents_root() / role


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_py_file(path: Path, contents: str):
    _write_file(path, contents)
    path.chmod(path.stat().st_mode | 0o111)


def _create_main_agent(path, agents_py_path: Path, agents_py: str, instructions_path: Path, instructions: str):
    _ensure_dir(path)
    _write_file(instructions_path, instructions)
    _write_py_file(agents_py_path, agents_py)


def _read_template_file(path: str) -> str:
    return resources.files(__package__).joinpath(path).read_text(encoding=ENCODING)


class TemplateFileProvider:
    def __init__(self, role_agent_script: str, agents_md_path: str, main_agent_script: str, main_instructions: str):
        self.role_agent_script = _read_template_file(role_agent_script)
        self.agents_md = _read_template_file(agents_md_path)
        self.main_agent_script = _read_template_file(main_agent_script)
        self.main_instructions = _read_template_file(main_instructions)


@dataclass
class FileNameProvider:
    agents_dir: str
    main_role: str
    agent_py: str
    agents_md: str
    instructions: str
    info: str


class Cli:
    def __init__(self, base: Path, file_name_provider: FileNameProvider, template_file_provider: TemplateFileProvider):
        self._file_name_provider: FileNameProvider = file_name_provider
        self._template_file_provider: TemplateFileProvider = template_file_provider
        self._base: Path = base
        self._agents_root = self._base / self._file_name_provider.agents_dir


    def _role_dir(self, role) -> Path:
        return self._agents_root / role


    def _create_main_agent(self):
        main_dir = self._role_dir(self._file_name_provider.main_role)
        _ensure_dir(main_dir)
        instructions_path = main_dir / self._file_name_provider.instructions
        agent_py_path = main_dir / self._file_name_provider.agent_py

        _write_file(instructions_path, self._template_file_provider.main_instructions)
        _write_py_file(agent_py_path, self._template_file_provider.main_agent_script)


    def _write_agents_md(self):
        _write_file(self._base / self._file_name_provider.agents_md, self._template_file_provider.agents_md)


    def init_command(self):
        """Initialize the myteam directory with default main role."""
        _ensure_dir(self._agents_root)
        self._write_agents_md()

        self._create_main_agent()


    def new_command(self, role: str):
        """Create a new role directory with placeholder files."""
        role_dir = self._agents_root / role
        if role_dir.exists():
            print(f"Role '{role}' already exists at {role_dir}", file=sys.stderr)
            exit(1)


        _ensure_dir(role_dir)
        (role_dir / self._file_name_provider.info).write_text("", encoding=ENCODING)
        (role_dir / self._file_name_provider.instructions).write_text("", encoding=ENCODING)
        agent_py = role_dir / self._file_name_provider.agent_py
        _write_py_file(agent_py, self._template_file_provider.role_agent_script)


    def remove_command(self, role: str):
        """Delete the directory for a role if it exists."""
        role_dir = self._role_dir(role)
        if not role_dir.exists():
            print(f"Role '{role}' not found at {role_dir}", file=sys.stderr)
            exit(1)

        if not role_dir.is_dir():
            print(f"Path for role '{role}' is not a directory: {role_dir}", file=sys.stderr)
            exit(1)

        try:
            shutil.rmtree(role_dir)
        except OSError as exc:
            print(f"Failed to remove role '{role}': {exc}", file=sys.stderr)
            exit(1)


    def get_role_command(self, role: str):
        """Print the instructions for the given role if available."""
        role_dir = self._role_dir(role)
        if not role_dir.exists():
            print(f"Role '{role}' not found. Run 'myteam new {role}' to create it.", file=sys.stderr)
            exit(1)

        agent_py = role_dir / self._file_name_provider.agent_py
        if agent_py.exists():
            try:
                result = subprocess.run([sys.executable, str(agent_py)], cwd=role_dir, check=False)
            except OSError as exc:
                print(f"Failed to execute {self._file_name_provider.agent_py} for role '{role}': {exc}", file=sys.stderr)
                exit(1)
            exit(result.returncode)

        print(f"No {self._file_name_provider.agent_py} found for role '{role}'.", file=sys.stderr)
        exit(1)


def version() -> str:
    return f"{APP_NAME} {__version__}"


def main(argv: list[str] | None = None):
    file_name_provider = FileNameProvider(
        agents_dir=".myteam",
        main_role="main",
        agent_py="agent.py",
        agents_md="AGENTS.md",
        instructions="instructions.md",
        info="info.md"
    )

    template_file_provider = TemplateFileProvider(
        role_agent_script="templates/role_agent_template.py",
        main_agent_script="templates/main_agent_template.py",
        agents_md_path="templates/agents_md_template.md",
        main_instructions="templates/main_instructions_template.md"
    )

    cli = Cli(
        base=Path.cwd(),
        file_name_provider=file_name_provider,
        template_file_provider=template_file_provider
    )

    commands = {
        "init": cli.init_command,
        "new": cli.new_command,
        "remove": cli.remove_command,
        "get-role": cli.get_role_command,
        "download": download,
        "list": list_available_items,
        "--version": version,
    }

    fire.Fire(commands)


if __name__ == "__main__":
    sys.exit(main())
