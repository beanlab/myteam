from pathlib import Path
from typing import Callable

from myteam.templates import get_template


def get_myteam_root(cur_dir: Path):
    d = cur_dir
    while d.parent != d:  # i.e. not at root
        if d.name == '.myteam':
            return d
        d = d.parent
    return cur_dir


def _print_block(text: str) -> None:
    print(text.rstrip('\n') + '\n')


def print_instructions(base: Path):
    for file in ['role.md', 'ROLE.md', 'skill.md', 'SKILL.md']:
        instructions_file = base / file
        if instructions_file.exists():
            _print_block(instructions_file.read_text(encoding='utf-8'))
            return


def is_role_dir(folder: Path) -> bool:
    return folder.is_dir() and (folder / 'role.md').exists()


def is_skill_dir(folder: Path) -> bool:
    return folder.is_dir() and (folder / 'skill.md').exists()


def _get_dir_info(folder: Path) -> str:
    info = folder / "info.md"
    if info.exists():
        return info.read_text(encoding="utf-8").rstrip('\n')


def _is_py_file(file: Path) -> bool:
    return file.is_file() and file.suffix == '.py'


def _print_info(
        header: str,
        folder: Path, base_dir: Path, ignore: list[str],
        is_relevant: Callable[[Path], bool],
        get_info: Callable[[Path], str],
        instructions: str
):
    relevant = list(sorted(
        p
        for p in folder.iterdir()
        if is_relevant(p) and p.name not in ignore
    ))
    if relevant:
        if instructions:
            _print_block(instructions)
        print()
        print(f' {header} '.center(30, '*'))
    for cur_dir in relevant:
        name = cur_dir.relative_to(base_dir).as_posix()
        print(f" {name} ".center(30, '-'))
        if (info := get_info(cur_dir)) is not None:
            print(info)
    if relevant:
        print()


def list_dir(folder: Path, base_dir: Path, ignore: list[str], include_instructions=True):
    # Sub roles
    _print_info('Team Members', folder, base_dir, ignore, is_role_dir, _get_dir_info,
                get_template('explain_roles.md') if include_instructions else '')

    # Skills
    _print_info('Skills', folder, base_dir, ignore, is_skill_dir, _get_dir_info,
                get_template('explain_skills.md') if include_instructions else '')

    _print_info('Tools', folder, base_dir, ignore + ['load.py'], _is_py_file, lambda f: '', '')
    # TODO - get usage from py file
