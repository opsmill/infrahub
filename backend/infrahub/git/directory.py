from pathlib import Path

from infrahub import config
from infrahub.log import get_logger

log = get_logger()


def get_repositories_directory() -> Path:
    """Return the absolute path to the main directory used for the repositories."""
    return Path(config.SETTINGS.git.repositories_directory).resolve()


def initialize_repositories_directory() -> bool:
    """Check if the main repositories_directory already exist, if not create it.

    Return
        True if the directory has been created,
        False if the directory was already present.
    """
    repos_dir = get_repositories_directory()
    if not repos_dir.exists():
        repos_dir.mkdir(parents=True)

        log.debug(f"Initialized the repositories_directory at {repos_dir}")
        return True

    log.debug(f"repositories_directory already present at {repos_dir}")
    return False
