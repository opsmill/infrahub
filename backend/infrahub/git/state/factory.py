from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import config

from .bus_reader import BusRepositoryGitStateReader

if TYPE_CHECKING:
    from infrahub.services.adapters.message_bus import InfrahubMessageBus

    from .reader import RepositoryGitStateReader


def build_repository_git_state_reader(message_bus: InfrahubMessageBus) -> RepositoryGitStateReader:
    """Return the reader every git-state consumer codes against.

    The only place an implementation is chosen or a setting is read.
    """
    if config.OVERRIDE.repository_git_state_reader:
        return config.OVERRIDE.repository_git_state_reader

    return BusRepositoryGitStateReader(message_bus=message_bus, timeout=config.SETTINGS.broker.rpc_timeout)
