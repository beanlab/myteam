import os
from pathlib import Path

MYTEAM_ROOT_DIR_ENV_VAR_NAME = "MYTEAM_DIRECTORY_ROOT"


def get_myteam_root():
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
