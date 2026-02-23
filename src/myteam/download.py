import json
import sys
import urllib.request
from pathlib import Path
from .constants import APP_NAME, ROSTER_REPOSITORY_URL, ROSTER_RAW_BASE_URL, AGENTS_DIRNAME


def _fetch_json(url: str) -> dict:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": APP_NAME})
        with urllib.request.urlopen(request) as response:
            return json.load(response)
    except Exception as exc:
        print(f"Failed to fetch JSON from {url}: {exc}", file=sys.stderr)
        exit(1)


def _handle_missing_roster(roster: str, roster_trees: list):
    roster_names = [entry.get("path") for entry in roster_trees if entry.get("type") == "tree"]
    roster_names.sort()
    available = ", ".join(roster_names) if roster_names else "none"
    print(f"Roster '{roster}' not found. Available rosters: {available}", file=sys.stderr)
    exit(1)


def _fetch_available_rosters():
    root_tree = _fetch_json(ROSTER_REPOSITORY_URL + "/main?recursive=1")
    trees =  root_tree.get("tree", [])
    # return [tree for tree in trees if tree.get('type') == "tree"]
    return trees


def _fetch_roster_tree(roster: str):
    roster_trees = _fetch_available_rosters()
    roster_tree = next(
        (entry for entry in roster_trees if entry.get("path") == roster),
        None,
    )
    if roster_tree is None:
        _handle_missing_roster(roster, roster_trees)

    return roster_tree


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


def _fetch_tree_files(roster_tree):
    subtree_url = f"{ROSTER_REPOSITORY_URL}/{roster_tree['sha']}?recursive=1"
    subtree = _fetch_json(subtree_url)
    file_entries = [entry for entry in subtree.get("tree", []) if entry.get("type") == "blob"]
    if not file_entries:
        print(f"No files found in roster '{roster_tree.get('path')}'.", file=sys.stderr)
        exit(1)

    return file_entries


def _download_tree_files(file_entries: list, tree_path: str, destination: Path):
    total = len(file_entries)
    for idx, entry in enumerate(file_entries, start=1):
        rel_path = entry.get("path")
        if not rel_path:
            continue
        raw_url = f"{ROSTER_RAW_BASE_URL}/{tree_path}/{rel_path}"
        print(f"\rDownloading {tree_path} {idx}/{total}", end="", file=sys.stderr)
        _download_file(raw_url, destination / rel_path)
    print("", file=sys.stderr)


def download(download_path: str, relative_destination: str = AGENTS_DIRNAME):
    destination = Path.cwd() / relative_destination
    roster_tree = _fetch_roster_tree(download_path)

    if roster_tree.get('type') == 'blob':
        file_name = roster_tree.get('path').split("/")[-1]
        _download_file(f"{ROSTER_RAW_BASE_URL}/{roster_tree.get('path')}", destination / file_name)
    else:
        tree_files = _fetch_tree_files(roster_tree)
        _download_tree_files(tree_files, download_path, destination)


def list_available_items():
    available_rosters = _fetch_available_rosters()
    roster_names = [roster.get('path') for roster in available_rosters]
    for name in roster_names:
        print(name)
