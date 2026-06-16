"""Embedded template assets for myteam."""
from pathlib import Path

_template_dir = Path(__file__).parent


def get_template_file(name: str) -> Path:
    return _template_dir / name


def get_template(name: str) -> str:
    template = get_template_file(name)
    return template.read_text()
