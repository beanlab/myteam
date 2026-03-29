"""Roster listing and download logic."""
from __future__ import annotations

import json
import sys
import urllib.request
from collections.abc import Iterable
from pathlib import Path

APP_NAME = "myteam"
AGENTS_DIRNAME = ".myteam"
DEFAULT_REPO = "beanlab/rosters"


def _agents_root(base: Path) -> Path:
    return base / AGENTS_DIRNAME


def _download_destination(base: Path, destination: Path | str | None) -> Path:
    if destination is None:
        return _agents_root(base)
    return Path(destination)


def _repo_urls(repo: str) -> tuple[str, str]:
    repo_path = repo.strip().strip("/")
    if repo_path.count("/") != 1:
        print(f"Invalid repo '{repo}'. Expected format: <owner>/<repo>.", file=sys.stderr)
        exit(1)
    api_base = f"https://api.github.com/repos/{repo_path}/git/trees"
    raw_base = f"https://raw.githubusercontent.com/{repo_path}/refs/heads/main"
    return api_base, raw_base


def _fetch_json(url: str) -> dict:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": APP_NAME})
        with urllib.request.urlopen(request) as response:
            return json.load(response)
    except Exception as exc:
        print(f"Failed to fetch JSON from {url}: {exc}", file=sys.stderr)
        exit(1)


def _download_file(url: str, output_path: Path):
    try:
        request = urllib.request.Request(url, headers={"User-Agent": APP_NAME})
        with urllib.request.urlopen(request) as response:
            data = response.read()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)
    except Exception as exc:
        print(f"Failed to download file from {url}: {exc}", file=sys.stderr)
        exit(1)


def _fetch_available_rosters(roster_repository_url: str):
    root_tree = _fetch_json(roster_repository_url + "/main?recursive=1")
    return root_tree.get("tree", [])


def _fetch_roster_entry(roster: str, roster_repository_url: str) -> dict:
    roster_trees = _fetch_available_rosters(roster_repository_url)
    roster_tree = next(
        (entry for entry in roster_trees if entry.get("path") == roster),
        None,
    )
    if roster_tree is None:
        _handle_missing_roster(roster, roster_trees)

    return roster_tree


def _handle_missing_roster(roster: str, roster_trees: list):
    roster_names = [entry.get("path") for entry in roster_trees if entry.get("type") == "tree"]
    roster_names.sort()
    available = ", ".join(roster_names) if roster_names else "none"
    print(f"Roster '{roster}' not found. Available rosters: {available}", file=sys.stderr)
    exit(1)


def _fetch_tree_files(roster_tree, roster_repository_url: str):
    subtree_url = f"{roster_repository_url}/{roster_tree['sha']}?recursive=1"
    subtree = _fetch_json(subtree_url)
    file_entries = [entry for entry in subtree.get("tree", []) if entry.get("type") == "blob"]
    if not file_entries:
        print(f"No files found in roster '{roster_tree.get('path')}'.", file=sys.stderr)
        exit(1)

    return file_entries


def _blob_destination(blob_object: dict, destination: Path) -> Path:
    file_name = blob_object.get("path", "").split("/")[-1]
    return destination / file_name


def _download_blob(blob_object: dict, destination: Path, roster_raw_base_url: str):
    output_path = _blob_destination(blob_object, destination)
    file_name = output_path.name
    print(f"\rDownloading {file_name}")
    _download_file(f"{roster_raw_base_url}/{blob_object.get('path')}", output_path)


def _tree_file_url(roster_dir_name: str, entry: dict, roster_raw_base_url: str) -> str:
    return f"{roster_raw_base_url}/{roster_dir_name}/{entry.get('path')}"


def _tree_file_destination(entry: dict, destination: Path) -> Path | None:
    rel_path = entry.get("path")
    if not rel_path:
        return None
    return destination / rel_path


def _download_tree_files(file_entries: Iterable[dict], roster_dir_name: str, destination: Path, roster_raw_base_url: str):
    file_entries = list(file_entries)
    total = len(file_entries)
    for idx, entry in enumerate(file_entries, start=1):
        output_path = _tree_file_destination(entry, destination)
        if output_path is None:
            continue
        print(f"\rDownloading {roster_dir_name} {idx}/{total}", end="", file=sys.stderr)
        _download_file(_tree_file_url(roster_dir_name, entry, roster_raw_base_url), output_path)
    print("", file=sys.stderr)


def _download_roster_entry(roster_entry: dict, roster_name: str, destination: Path, roster_repository_url: str, roster_raw_base_url: str):
    if roster_entry.get("type") == "blob":
        _download_blob(roster_entry, destination, roster_raw_base_url)
        return
    tree_files = _fetch_tree_files(roster_entry, roster_repository_url)
    _download_tree_files(tree_files, roster_name, destination, roster_raw_base_url)


def download_roster(
    roster_dir_name: str,
    destination: Path | str | None = None,
    repo: str = DEFAULT_REPO,
):
    base = Path.cwd()
    destination = _download_destination(base, destination)
    roster_repository_url, roster_raw_base_url = _repo_urls(repo)
    roster_entry = _fetch_roster_entry(roster_dir_name, roster_repository_url)
    _download_roster_entry(roster_entry, roster_dir_name, destination, roster_repository_url, roster_raw_base_url)


def list_available_rosters(repo: str = DEFAULT_REPO):
    roster_repository_url, _ = _repo_urls(repo)
    available_rosters = _fetch_available_rosters(roster_repository_url)
    roster_names = [roster.get("path") for roster in available_rosters]
    for name in roster_names:
        print(name)
