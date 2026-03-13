"""Embedded template assets for myteam."""
from pathlib import Path

_template_dir = Path(__file__).parent


def get_template(name: str) -> str:
    template = _template_dir / name
    return template.read_text()
