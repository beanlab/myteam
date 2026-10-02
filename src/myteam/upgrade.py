"""Helpers for tracking and explaining `.myteam` upgrades."""
from __future__ import annotations

import re
from importlib.resources import files
from pathlib import Path

from . import __version__

ENCODING = 'utf-8'
TRACKED_VERSION_FILENAME = ".myteam-version"
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
_CHANGELOG_HEADING_RE = re.compile(r"^##\s+(\d+\.\d+\.\d+)\s*$")


def tracked_version_file(myteam_root: Path) -> Path:
    return myteam_root / TRACKED_VERSION_FILENAME


def tracked_version_info(myteam_root: Path) -> tuple[str | None, str]:
    version_file = tracked_version_file(myteam_root)
    if not version_file.exists():
        return None, "untracked legacy version"

    raw_version = version_file.read_text(encoding=ENCODING).strip()
    if not raw_version:
        return None, "untracked legacy version"
    if not _SEMVER_RE.match(raw_version):
        return None, f"invalid tracked version '{raw_version}'"
    return raw_version, raw_version


def read_tracked_version(myteam_root: Path) -> str | None:
    version, _ = tracked_version_info(myteam_root)
    return version


def write_tracked_version(myteam_root: Path, version: str = __version__) -> None:
    tracked_version_file(myteam_root).write_text(f"{version}\n", encoding=ENCODING)


def _parse_version(version: str) -> tuple[int, int, int]:
    if not _SEMVER_RE.match(version):
        raise ValueError(f"Unsupported version format: {version}")
    major, minor, patch = version.split(".")
    return int(major), int(minor), int(patch)


def packaged_changelog_text() -> str:
    packaged_changelog = files("myteam").joinpath("CHANGELOG.md")
    return packaged_changelog.read_text(encoding=ENCODING)


def _parse_changelog_sections() -> list[tuple[str, str]]:
    lines = packaged_changelog_text().splitlines()

    sections: list[tuple[str, str]] = []
    current_version: str | None = None
    current_lines: list[str] = []

    for line in lines:
        match = _CHANGELOG_HEADING_RE.match(line)
        if match is not None:
            if current_version is not None:
                sections.append((current_version, "\n".join(current_lines).strip()))
            current_version = match.group(1)
            current_lines = [line]
            continue
        if current_version is not None:
            current_lines.append(line)

    if current_version is not None:
        sections.append((current_version, "\n".join(current_lines).strip()))
    return sections


def format_release_notes(myteam_root: Path, current_version: str = __version__) -> str:
    tracked_version, tracked_label = tracked_version_info(myteam_root)
    current = _parse_version(current_version)
    if tracked_version is None:
        relevant = [
            section
            for version, section in _parse_changelog_sections()
            if _parse_version(version) <= current
        ]
    else:
        tracked = _parse_version(tracked_version)
        relevant = [
            section
            for version, section in _parse_changelog_sections()
            if tracked < _parse_version(version) <= current
        ]

    if not relevant:
        return "No newer `myteam` changelog entries are available for this `.myteam` tree.\n"

    heading = f"New `myteam` features since {tracked_label}:\n"
    return heading + "\n\n".join(relevant).rstrip() + "\n"


def print_release_notes(myteam_root: Path) -> None:
    print(format_release_notes(myteam_root), end="")


def print_upgrade_notice(myteam_root: Path, current_version: str = __version__) -> None:
    tracked_version, tracked_label = tracked_version_info(myteam_root)
    if tracked_version is not None and _parse_version(tracked_version) >= _parse_version(current_version):
        return

    print(" Upgrade Available ".center(30, "*"))
    if tracked_version is None:
        print(
            f"This `.myteam` tree is tracked as {tracked_label}. "
            f"You are running myteam {current_version}."
        )
    else:
        print(
            f"This `.myteam` tree is tracked at myteam {tracked_version}, "
            f"but the installed version is {current_version}."
        )
    print("The agent can assist with reviewing this existing `.myteam` tree if you want to proceed.")
    print(
        "Run `myteam changelog` for release notes, "
        "and apply approved project-specific updates manually.\n"
    )
