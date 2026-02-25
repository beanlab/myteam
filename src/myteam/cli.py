"""Command-line interface for the myteam package."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
import fire

from . import __version__


APP_NAME = "myteam"
DEFAULT_ROLE = "main"
AGENTS_DIRNAME = ".myteam"
ENCODING = "utf-8"
INSTRUCTIONS_FILE = "instructions.md"
INFO_FILE = "info.md"
AGENT_PY_FILE = "agent.py"
AGENTS_MD_FILE = "AGENTS.md"
ROSTER_REPOSITORY_URL = "https://api.github.com/repos/beanlab/rosters/git/trees"
ROSTER_RAW_BASE_URL = "https://raw.githubusercontent.com/beanlab/rosters/refs/heads/main"
ZIP_FILE_NAME = "roster.zip"
ROLE_AGENT_SCRIPT_TEMPLATE = "templates/role_agent_template.py"
MAIN_AGENT_SCRIPT_TEMPLATE = "templates/main_agent_template.py"
AGENTS_MD_TEMPLATE = "templates/agents_md_template.md"
MAIN_INSTRUCTIONS_TEMPLATE = "templates/main_instructions_template.md"


def _download_file(url: str, output_path: Path):
    try:
        request = urllib.request.Request(url)
        with urllib.request.urlopen(request) as response:
            data = response.read()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)
    except Exception as exc:
        print(f"Failed to download file from {url}: {exc}", file=sys.stderr)
        exit(1)


def _handle_missing_roster(roster: str, roster_trees: list):
    roster_names = [entry.get("path") for entry in roster_trees if entry.get("type") == "tree"]
    roster_names.sort()
    available = ", ".join(roster_names) if roster_names else "none"
    print(f"Roster '{roster}' not found. Available rosters: {available}", file=sys.stderr)
    exit(1)


def _fetch_json(url: str) -> dict:
    try:
        request = urllib.request.Request(url)
        with urllib.request.urlopen(request) as response:
            return json.load(response)
    except Exception as exc:
        print(f"Failed to fetch JSON from {url}: {exc}", file=sys.stderr)
        exit(1)

def _write_file(path: Path, content: str):
    path.write_text(content, encoding=ENCODING)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_py_file(path: Path, contents: str):
    _write_file(path, contents)
    path.chmod(path.stat().st_mode | 0o111)


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


class DownloadCli:
    def __init__(self, agents_dir: Path, roster_repo_url: str, roster_download_url: str):
        self._agents_dir = agents_dir
        self._roster_repo_url: str = roster_repo_url
        self._roster_download_url: str = roster_download_url


    def _fetch_available_rosters(self):
        root_tree = _fetch_json(self._roster_repo_url + "/main?recursive=1")
        trees = root_tree.get("tree", [])
        return trees


    def _fetch_roster_tree(self, roster: str):
        roster_trees = self._fetch_available_rosters()
        roster_tree = next(
            (entry for entry in roster_trees if entry.get("path") == roster),
            None,
        )
        if roster_tree is None:
            _handle_missing_roster(roster, roster_trees)

        return roster_tree


    def _fetch_tree_files(self, roster_tree):
        subtree_url = f"{self._roster_repo_url}/{roster_tree['sha']}?recursive=1"
        subtree = _fetch_json(subtree_url)
        file_entries = [entry for entry in subtree.get("tree", []) if entry.get("type") == "blob"]
        if not file_entries:
            print(f"No files found in roster '{roster_tree.get('path')}'.", file=sys.stderr)
            exit(1)

        return file_entries


    def _download_blob(self, roster_tree, destination):
        file_name = roster_tree.get('path').split("/")[-1]
        _download_file(f"{self._roster_download_url}/{roster_tree.get('path')}", destination / file_name)


    def _download_tree_files(self, file_entries: list, tree_path: str, destination: Path):
        total = len(file_entries)
        for idx, entry in enumerate(file_entries, start=1):
            rel_path = entry.get("path")
            if not rel_path:
                continue
            raw_url = f"{self._roster_download_url}/{tree_path}/{rel_path}"
            print(f"\rDownloading {tree_path} {idx}/{total}", end="", file=sys.stderr)
            _download_file(raw_url, destination / rel_path)
        print("", file=sys.stderr)


    def _download_roster_files(self, download_path, roster_tree, destination):
        if roster_tree.get('type') == 'blob':
            self._download_blob(roster_tree, destination)
        else:
            tree_files = self._fetch_tree_files(roster_tree)
            self._download_tree_files(tree_files, download_path, destination)


    def download(self, download_path: str, relative_destination: str | None = None):
        destination = self._agents_dir if relative_destination is None else Path(relative_destination).resolve()

        roster_tree = self._fetch_roster_tree(download_path)
        self._download_roster_files(download_path, roster_tree, destination)


    def list_available_items(self):
        available_rosters = self._fetch_available_rosters()
        roster_names = [roster.get('path') for roster in available_rosters]
        for name in roster_names:
            print(name)


def version() -> str:
    return f"{APP_NAME} {__version__}"


def main():
    base = Path.cwd()

    file_name_provider = FileNameProvider(
        agents_dir=AGENTS_DIRNAME,
        main_role=DEFAULT_ROLE,
        agent_py=AGENT_PY_FILE,
        agents_md=AGENTS_MD_FILE,
        instructions=INSTRUCTIONS_FILE,
        info=INFO_FILE
    )

    template_file_provider = TemplateFileProvider(
        role_agent_script=ROLE_AGENT_SCRIPT_TEMPLATE,
        main_agent_script=MAIN_AGENT_SCRIPT_TEMPLATE,
        agents_md_path=AGENTS_MD_TEMPLATE,
        main_instructions=MAIN_INSTRUCTIONS_TEMPLATE
    )

    cli = Cli(
        base=base,
        file_name_provider=file_name_provider,
        template_file_provider=template_file_provider
    )

    download_cli = DownloadCli(
        agents_dir= base / file_name_provider.agents_dir,
        roster_repo_url=ROSTER_REPOSITORY_URL,
        roster_download_url=ROSTER_RAW_BASE_URL
    )

    commands = {
        "init": cli.init_command,
        "new": cli.new_command,
        "remove": cli.remove_command,
        "get-role": cli.get_role_command,
        "download": download_cli.download,
        "list": download_cli.list_available_items,
        "--version": version,
    }

    fire.Fire(commands)


if __name__ == "__main__":
    sys.exit(main())
