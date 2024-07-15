import os

from infrahub import config
from infrahub.log import get_logger

log = get_logger()


def get_repositories_directory() -> str:
    """Return the absolute path to the main directory used for the repositories."""
    repos_dir = config.SETTINGS.git.repositories_directory
    if not os.path.isabs(repos_dir):
        current_dir = os.getcwd()
        repos_dir = os.path.join(current_dir, config.SETTINGS.git.repositories_directory)

    return str(repos_dir)


def initialize_repositories_directory() -> bool:
    """Check if the main repositories_directory already exist, if not create it.

    Return
        True if the directory has been created,
        False if the directory was already present.
    """
    repos_dir = get_repositories_directory()
    if not os.path.isdir(repos_dir):
        os.makedirs(repos_dir)
        log.debug(f"Initialized the repositories_directory at {repos_dir}")
        return True

    log.debug(f"Repositories_directory already present at {repos_dir}")
    return False
