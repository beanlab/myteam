import os
from pathlib import Path

MYTEAM_ROOT_DIR_ENV_VAR_NAME = "MYTEAM_DIRECTORY_ROOT"


def relative_to_myteam(file: Path) -> str:
    return str(file.relative_to(get_myteam_root()).stem)


def resolve_prefix(prefix: str) -> Path:
    return get_myteam_root().joinpath(prefix).resolve().absolute()


def resolve_target(name: str) -> Path:
    # Is this a builtin? # TODO
    # yes -> return path to builtin py file
    # Find the file this references
    stub = resolve_prefix(name)
    if stub.exists():
        return stub

    for ext in ['.py', '.md']:
        if (file := stub.with_suffix(ext)).exists():
            return file

    raise FileNotFoundError(name)


def get_myteam_root() -> Path:
    """Return the root .myteam folder"""
    configured_root = os.environ.get(MYTEAM_ROOT_DIR_ENV_VAR_NAME)
    if not configured_root:
        raise RuntimeError(f'Talk to the devs')  # TODO - better error
    return Path(configured_root)

    # TODO - this logic may be obsolete if all tooling uses the env var
    # d = cur_dir
    # while d.parent != d:
    #     if d.name == ".myteam":
    #         return d
    #     d = d.parent
    # return cur_dir


def _find_myteam_folder(prefix: str) -> Path:
    folder = Path(prefix).resolve().absolute()
    if not folder.exists():
        raise FileNotFoundError(prefix)
    return folder


def _set_global_prefix_env_var(prefix: str):
    myteam_folder = _find_myteam_folder(prefix)
    os.environ[MYTEAM_ROOT_DIR_ENV_VAR_NAME] = str(myteam_folder)
