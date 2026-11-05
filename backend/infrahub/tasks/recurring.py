from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import config, lock

from .registry import refresh_branches

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices


async def trigger_branch_refresh(service: InfrahubServices) -> None:
    service.log.debug("Running branch refresh task")
    async with service.database.start_session() as db:
        await refresh_branches(db=db)

    await service.component.refresh_schema_hash()


async def close_idle_cache_connections(service: InfrahubServices) -> None:
    """Close the connections of this process's cache and lock pools that have been idle past the configured timeout."""
    idle_seconds = config.SETTINGS.cache.idle_connection_timeout
    await service.cache.close_idle_connections(idle_seconds=idle_seconds)
    if lock.registry is not None:
        await lock.registry.close_idle_connections(idle_seconds=idle_seconds)
