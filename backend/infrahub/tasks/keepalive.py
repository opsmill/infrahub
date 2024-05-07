from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices


async def refresh_heartbeat(service: InfrahubServices) -> None:
    """Update API server worker information in the cache

    The goal of this job is to provide an updated list of API server workers in the cache, it will have a freshness
    of 15 seconds after which workers that haven't updated their entry in the cache will be removed.

    The function also keeps the primary API server ID up to date. The primary ID is used within other tasks to ensure
    that only one worker is responsible for scheduling specific tasks.
    """
    service.log.debug("Refreshing API workers in cache")
    await service.component.refresh_heartbeat()
