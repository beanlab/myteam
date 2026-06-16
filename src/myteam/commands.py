"""Command implementations for the myteam CLI."""
from __future__ import annotations

import sys
from pathlib import Path


APP_NAME = 'myteam'
GOVERNING_DOCS_ROOT = Path(__file__).resolve().parents[1] / "governing_docs"


def version() -> str:
    from . import __version__

    return f"{APP_NAME} {__version__}"


def changelog() -> str:
    from .upgrade import packaged_changelog_text

    return packaged_changelog_text().rstrip()


def onboard(root: str | Path | None = None) -> str:
    docs_root = Path(root) if root is not None else GOVERNING_DOCS_ROOT
    docs_root = docs_root.resolve()

    if not docs_root.exists() or not docs_root.is_dir():
        print(f"Not a governing docs folder: {docs_root}", file=sys.stderr)
        raise SystemExit(1)

    files = _ordered_governing_docs(docs_root)
    return "\n\n".join(_format_document(file, docs_root) for file in files)


def _ordered_governing_docs(root: Path) -> list[Path]:
    overview = root / "application-overview.md"
    files = [overview] if overview.exists() and overview.is_file() else []
    files.extend(
        sorted(
            (
                path
                for path in root.rglob("*")
                if path.is_file() and path != overview
            ),
            key=lambda path: path.relative_to(root).as_posix().lower(),
        )
    )
    return files


def _format_document(file: Path, root: Path) -> str:
    relative_name = file.relative_to(root).as_posix()
    body = file.read_text(encoding="utf-8").rstrip("\n")
    if not body:
        return f"----{relative_name}----"
    return f"----{relative_name}----\n{body}"
