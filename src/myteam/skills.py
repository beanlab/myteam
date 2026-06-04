import functools
import subprocess
import sys
from pathlib import Path
from typing import TypedDict

from .frontmatter import split_markdown_frontmatter
from .prefix import resolve_target, resolve_prefix, relative_to_myteam
from .templates import get_template


class SkillInfo(TypedDict):
    name: str
    """Name by which this skill is identified"""
    description: str
    content: str


def explain_skills() -> str:
    return get_template('explain_skills.md')


def _parse_skill_info(name: str, frontmatter: dict, content: str) -> SkillInfo:
    skill = SkillInfo(name=name, **frontmatter, content=content)
    return skill


def _get_skills(prefix: str) -> list[SkillInfo]:
    """List the skill headers for all skills under `prefix`"""
    skill_infos = []
    for file in resolve_prefix(prefix).glob('*'):
        if file.is_dir():
            continue

        frontmatter, content = split_markdown_frontmatter(file.read_text())
        if frontmatter.get('type') == 'skill':
            skill_name = relative_to_myteam(file)
            info = _parse_skill_info(skill_name, frontmatter, content)
            skill_infos.append(info)

    return skill_infos


def _format_skills(skill_info: list[SkillInfo]) -> str:
    if not skill_info:
        return ""

    lines = [f" Skills ".center(30, "*")]
    for skill in skill_info:
        lines.append(f" {skill['name']} ".center(30, "-"))
        if desc := skill.get('description'):
            lines.append(desc)
    return "\n".join(lines)


def get_skills(prefix: str) -> str:
    infos = _get_skills(prefix)
    return _format_skills(infos)


@functools.wraps(get_skills)
def print_get_skills(*args, **kwargs):
    print(get_skills(*args, **kwargsargs))


def _load_markdown_skill(skill_file: Path) -> str:
    frontmatter, content = split_markdown_frontmatter(skill_file.read_text())
    return content


def _load_python_skill(skill_file: Path):
    result = subprocess.run(
        [sys.executable, str(skill_file)],
        cwd=skill_file.parent,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
    )
    # TODO - do something with stderr?
    return result.stdout


def _load_skill(skill_file: Path) -> str:
    if skill_file.suffix == '.md':
        return _load_markdown_skill(skill_file)

    elif skill_file.suffix == '.py':
        return _load_python_skill(skill_file)

    else:
        raise NotImplementedError(skill_file)


def load_skill(skill: str) -> str:
    """Return the instructions for the given skill if available."""
    skill_file = resolve_target(skill)
    return _load_skill(skill_file)


def new_skill(skill_name: str):
    resolve_prefix(skill_name).write_text(get_template('new_skill.md'))


@functools.wraps(load_skill)
def print_load_skill(*args, **kwargs):
    print(load_skill(*args, **kwargs))
