"""Roster listing and download logic."""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

APP_NAME = "myteam"
AGENTS_DIRNAME = ".myteam"
DEFAULT_REPO = "beanlab/rosters"


def _agents_root(base: Path) -> Path:
    return base / AGENTS_DIRNAME


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
    root_tree = _fetch_json(roster_repository_url + "/main")
    trees = root_tree.get("tree", [])
    return [tree for tree in trees if tree.get("type") == "tree"]


def _fetch_roster_tree(roster: str, roster_repository_url: str):
    roster_trees = _fetch_available_rosters(roster_repository_url)
    roster_tree = next(
        (entry for entry in roster_trees if entry.get("path") == roster and entry.get("type") == "tree"),
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


def _download_tree_files(file_entries, roster_dir_name: str, base: Path, roster_raw_base_url: str):
    total = len(file_entries)
    for idx, entry in enumerate(file_entries, start=1):
        rel_path = entry.get("path")
        if not rel_path:
            continue
        raw_url = f"{roster_raw_base_url}/{roster_dir_name}/{rel_path}"
        print(f"\rDownloading {roster_dir_name} {idx}/{total}", end="", file=sys.stderr)
        _download_file(raw_url, _agents_root(base) / rel_path)
    print("", file=sys.stderr)


def download_roster(roster_dir_name: str, repo: str = DEFAULT_REPO):
    base = Path.cwd()
    roster_repository_url, roster_raw_base_url = _repo_urls(repo)
    roster_tree = _fetch_roster_tree(roster_dir_name, roster_repository_url)
    tree_files = _fetch_tree_files(roster_tree, roster_repository_url)
    _download_tree_files(tree_files, roster_dir_name, base, roster_raw_base_url)


def list_available_rosters(repo: str = DEFAULT_REPO):
    roster_repository_url, _ = _repo_urls(repo)
    available_rosters = _fetch_available_rosters(roster_repository_url)
    roster_names = [roster.get("path") for roster in available_rosters]
    for name in roster_names:
        print(name)
