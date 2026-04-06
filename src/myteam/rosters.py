"""Roster listing and download logic."""
from __future__ import annotations

import json
import shutil
import sys
import urllib.request
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import yaml

from .paths import APP_NAME, DEFAULT_LOCAL_ROOT, agents_root, normalize_local_root

DEFAULT_REPO = "beanlab/rosters"
SOURCE_METADATA = ".source.yml"
DEFAULT_REF = "main"


def _selected_root(base: Path, prefix: str | Path | None = None) -> Path:
    try:
        return agents_root(base, prefix)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        exit(1)


def _download_destination(base: Path, roster: str, destination: Path | str | None, prefix: str | Path | None = None) -> Path:
    local_root = _selected_root(base, prefix)
    if destination is None:
        return local_root / Path(roster)
    return local_root / Path(destination)


def _display_path(base: Path, path: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def _repo_urls(repo: str, ref: str = DEFAULT_REF) -> tuple[str, str]:
    repo_path = repo.strip().strip("/")
    if repo_path.count("/") != 1:
        print(f"Invalid repo '{repo}'. Expected format: <owner>/<repo>.", file=sys.stderr)
        exit(1)
    api_base = f"https://api.github.com/repos/{repo_path}/git/trees"
    raw_base = f"https://raw.githubusercontent.com/{repo_path}/{ref}"
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


def _fetch_available_rosters(roster_repository_url: str, ref: str = DEFAULT_REF):
    root_tree = _fetch_json(f"{roster_repository_url}/{ref}?recursive=1")
    return root_tree.get("tree", [])


def _fetch_roster_entry(roster: str, roster_repository_url: str, ref: str = DEFAULT_REF) -> dict:
    roster_trees = _fetch_available_rosters(roster_repository_url, ref)
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


def _require_tree_roster(roster_entry: dict, roster_name: str) -> None:
    if roster_entry.get("type") == "tree":
        return
    print(f"Roster '{roster_name}' is a file. Only folder rosters are supported.", file=sys.stderr)
    exit(1)


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


def _source_metadata_path(destination: Path) -> Path:
    return destination / SOURCE_METADATA


def _read_source_metadata(destination: Path) -> dict[str, str] | None:
    metadata_path = _source_metadata_path(destination)
    if not metadata_path.exists():
        return None
    try:
        loaded = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    if not isinstance(loaded, dict):
        return None
    return {str(key): str(value) for key, value in loaded.items() if value is not None}


def _same_source(existing_metadata: dict[str, str] | None, repo: str, roster_name: str) -> bool:
    if existing_metadata is None:
        return False
    return existing_metadata.get("repo") == repo and existing_metadata.get("roster") == roster_name


def _ensure_destination_available(base: Path, destination: Path, repo: str, roster_name: str) -> None:
    if not destination.exists():
        return
    display_path = _display_path(base, destination)
    if _same_source(_read_source_metadata(destination), repo, roster_name):
        print(
            f"Managed download already exists at {display_path}. Run `myteam update {display_path}` instead.",
            file=sys.stderr,
        )
        exit(1)
    print(
        f"Unrelated content already exists at {display_path}; delete it or choose a different destination.",
        file=sys.stderr,
    )
    exit(1)


def _source_metadata(base: Path, destination: Path, repo: str, roster_name: str) -> dict[str, str]:
    return {
        "repo": repo,
        "roster": roster_name,
        "ref": DEFAULT_REF,
        "local_path": _display_path(base, destination),
        "downloaded_at": datetime.now(UTC).isoformat(),
    }


def _write_source_metadata(base: Path, destination: Path, repo: str, roster_name: str) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    metadata = _source_metadata(base, destination, repo, roster_name)
    _source_metadata_path(destination).write_text(yaml.safe_dump(metadata, sort_keys=True), encoding="utf-8")


def _replace_managed_destination(destination: Path) -> None:
    if not destination.exists():
        return
    if not destination.is_dir():
        print(f"Managed destination is not a directory: {destination}", file=sys.stderr)
        exit(1)
    shutil.rmtree(destination)


def _install_roster_tree(
    *,
    base: Path,
    destination: Path,
    repo: str,
    roster_dir_name: str,
    ref: str = DEFAULT_REF,
    replace_existing: bool = False,
) -> None:
    roster_repository_url, roster_raw_base_url = _repo_urls(repo, ref)
    roster_entry = _fetch_roster_entry(roster_dir_name, roster_repository_url, ref)
    _require_tree_roster(roster_entry, roster_dir_name)
    if replace_existing:
        _replace_managed_destination(destination)
    else:
        _ensure_destination_available(base, destination, repo, roster_dir_name)
    tree_files = _fetch_tree_files(roster_entry, roster_repository_url)
    _download_tree_files(tree_files, roster_dir_name, destination, roster_raw_base_url)
    _write_source_metadata(base, destination, repo, roster_dir_name)


def _require_source_metadata(destination: Path) -> dict[str, str]:
    metadata = _read_source_metadata(destination)
    if metadata is None:
        print(f"Managed download metadata not found at {_display_path(Path.cwd(), destination)}.", file=sys.stderr)
        exit(1)
    required_keys = ("repo", "roster", "ref")
    missing_keys = [key for key in required_keys if not metadata.get(key)]
    if missing_keys:
        missing = ", ".join(missing_keys)
        print(
            f"Managed download metadata at {_display_path(Path.cwd(), destination)} is missing required fields: {missing}.",
            file=sys.stderr,
        )
        exit(1)
    return metadata


def _managed_roots(base: Path, prefix: str | Path | None = None) -> list[Path]:
    root = _selected_root(base, prefix)
    if not root.exists():
        return []
    return sorted(metadata_path.parent for metadata_path in root.rglob(SOURCE_METADATA))


def _update_target(base: Path, path: Path | str, prefix: str | Path | None = None) -> Path:
    local_root = _selected_root(base, prefix)
    local_root_relative = normalize_local_root(prefix)
    raw_path = Path(path)
    if raw_path.is_absolute():
        try:
            raw_path.relative_to(local_root)
            return raw_path
        except ValueError:
            print(f"Managed download paths must live under {_display_path(base, local_root)}.", file=sys.stderr)
            exit(1)
    if raw_path.parts[: len(local_root_relative.parts)] == local_root_relative.parts:
        return base / raw_path
    return local_root / raw_path


def download_roster(
    roster_dir_name: str,
    destination: Path | str | None = None,
    repo: str = DEFAULT_REPO,
    prefix: str = DEFAULT_LOCAL_ROOT,
):
    base = Path.cwd()
    destination = _download_destination(base, roster_dir_name, destination, prefix)
    _install_roster_tree(base=base, destination=destination, repo=repo, roster_dir_name=roster_dir_name)


def update_roster(path: Path | str | None = None, prefix: str = DEFAULT_LOCAL_ROOT) -> None:
    base = Path.cwd()
    local_root = _selected_root(base, prefix)
    targets = _managed_roots(base, prefix) if path is None else [_update_target(base, path, prefix)]
    if not targets:
        print(f"No managed downloads found under {_display_path(base, local_root)}.", file=sys.stderr)
        exit(1)
    for destination in targets:
        metadata = _require_source_metadata(destination)
        _install_roster_tree(
            base=base,
            destination=destination,
            repo=metadata["repo"],
            roster_dir_name=metadata["roster"],
            ref=metadata["ref"],
            replace_existing=True,
        )


def list_available_rosters(repo: str = DEFAULT_REPO):
    roster_repository_url, _ = _repo_urls(repo)
    available_rosters = _fetch_available_rosters(roster_repository_url)
    roster_names = [roster.get("path") for roster in available_rosters]
    for name in roster_names:
        print(name)
