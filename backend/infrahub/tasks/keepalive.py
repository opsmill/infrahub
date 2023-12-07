from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.timestamp import Timestamp
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices


async def refresh_api_server_components(service: InfrahubServices) -> None:
    service.log.info("Refreshing API workers in cache")

    result = await service.cache.set(
        key=f"api_server:{WORKER_IDENTITY}", value=str(Timestamp()), expires=15, not_exists=True
    )

    result = await service.cache.set(key="primary_api_server_id", value=WORKER_IDENTITY, expires=15, not_exists=True)
    if result:
        service.log.info("Set primary API server")
    if not result:
        service.log.info("Primary node already set")
        primary_id = await service.cache.get(key="primary_api_server_id")
        if primary_id == WORKER_IDENTITY:
            service.log.info("Primary node set but same as ours, refreshing lifetime")
            await service.cache.set(key="primary_api_server_id", value=WORKER_IDENTITY, expires=15)
