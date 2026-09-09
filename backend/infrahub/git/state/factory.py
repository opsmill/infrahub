from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import config

from .reader import UnavailableRepositoryGitStateReader

if TYPE_CHECKING:
    from .reader import RepositoryGitStateReader


def build_repository_git_state_reader() -> RepositoryGitStateReader:
    """Return the reader every git-state consumer codes against.

    The only place an implementation is chosen or a setting is read.
    """
    if config.OVERRIDE.repository_git_state_reader:
        return config.OVERRIDE.repository_git_state_reader

    return UnavailableRepositoryGitStateReader()
