"""Helpers for tracking and explaining `.myteam` upgrades."""
from __future__ import annotations

import re
from pathlib import Path

from . import __version__
from .paths import ENCODING
from .templates import get_template

TRACKED_VERSION_FILENAME = ".myteam-version"
BUILTIN_SKILL_PATH = ("myteam",)
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


def _sorted_versions(versions: list[str]) -> list[str]:
    return sorted(versions, key=_parse_version)


def available_migration_versions(current_version: str = __version__) -> list[str]:
    migration_dir = Path(__file__).resolve().parent / "migrations"
    versions = [
        path.stem
        for path in migration_dir.glob("*.md")
        if _SEMVER_RE.match(path.stem) and _parse_version(path.stem) <= _parse_version(current_version)
    ]
    return _sorted_versions(versions)


def pending_migration_versions(
    tracked_version: str | None,
    current_version: str = __version__,
) -> list[str]:
    current = _parse_version(current_version)
    if tracked_version is None:
        return [version for version in available_migration_versions(current_version) if _parse_version(version) <= current]
    tracked = _parse_version(tracked_version)
    return [
        version
        for version in available_migration_versions(current_version)
        if tracked < _parse_version(version) <= current
    ]


def _migration_text(version: str) -> str:
    migration_file = Path(__file__).resolve().parent / "migrations" / f"{version}.md"
    return migration_file.read_text(encoding=ENCODING).rstrip()


def format_pending_migrations(myteam_root: Path) -> str:
    tracked_version, tracked_label = tracked_version_info(myteam_root)
    pending_versions = pending_migration_versions(tracked_version)
    if not pending_versions:
        return "No packaged `.myteam` migrations are pending.\n"

    blocks = [
        f"Pending migrations for `.myteam` tracked at {tracked_label}:\n"
    ]
    for index, version in enumerate(pending_versions):
        if index:
            blocks.append("")
        blocks.append(_migration_text(version))
    return "\n".join(blocks).rstrip() + "\n"


def _parse_changelog_sections() -> list[tuple[str, str]]:
    changelog = Path(__file__).resolve().parents[1] / "CHANGELOG.md"
    lines = changelog.read_text(encoding=ENCODING).splitlines()

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


def print_pending_migrations(myteam_root: Path) -> None:
    print(format_pending_migrations(myteam_root), end="")


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
    print("Load `myteam/migrate` for packaged migration guidance and `myteam/changelog` for release notes.")
    print("Apply any approved project-specific updates manually, then update the tracked version as part of those edits.\n")


def ensure_builtin_upgrade_skills(myteam_root: Path, overwrite: bool = False) -> list[str]:
    created: list[str] = []
    builtin_root = myteam_root.joinpath(*BUILTIN_SKILL_PATH)
    builtin_specs = (
        (
            builtin_root,
            {
                "skill.md": get_template("builtin_myteam_skill_definition.md"),
                "load.py": get_template("skill_load_template.py"),
            },
            "myteam",
        ),
        (
            builtin_root / "migrate",
            {
                "skill.md": get_template("builtin_migrate_skill_definition.md"),
                "load.py": get_template("builtin_migrate_skill_load_template.py"),
            },
            "myteam/migrate",
        ),
        (
            builtin_root / "changelog",
            {
                "skill.md": get_template("builtin_changelog_skill_definition.md"),
                "load.py": get_template("builtin_changelog_skill_load_template.py"),
            },
            "myteam/changelog",
        ),
    )

    for directory, files, display_name in builtin_specs:
        directory.mkdir(parents=True, exist_ok=True)
        for filename, contents in files.items():
            path = directory / filename
            if overwrite or not path.exists():
                path.write_text(contents, encoding=ENCODING)
        created.append(display_name)

    return created

