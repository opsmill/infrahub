from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from infrahub.core.timestamp import Timestamp
from infrahub.message_bus import messages
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices


async def refresh_api_server_components(service: InfrahubServices, expiration: Optional[int] = None) -> None:  # pylint: disable=unused-argument
    """Update API server worker information in the cache

    The goal of this job is to provide an updated list of API server workers in the cache, it will have a freshness
    of 15 seconds after which workers that haven't updated their entry in the cache will be removed.

    The function also keeps the primary API server ID up to date. The primary ID is used within other tasks to ensure
    that only one worker is responsible for scheduling specific tasks.
    """
    service.log.debug("Refreshing API workers in cache")

    await service.cache.set(key=f"api_server:{WORKER_IDENTITY}", value=str(Timestamp()), expires=15)

    result = await service.cache.set(key="primary_api_server_id", value=WORKER_IDENTITY, expires=15, not_exists=True)
    if result:
        await service.send(message=messages.EventWorkerNewPrimaryAPI(worker_id=WORKER_IDENTITY))
    else:
        service.log.debug("Primary node already set")
        primary_id = await service.cache.get(key="primary_api_server_id")
        if primary_id == WORKER_IDENTITY:
            service.log.debug("Primary node set but same as ours, refreshing lifetime")
            await service.cache.set(key="primary_api_server_id", value=WORKER_IDENTITY, expires=15)
