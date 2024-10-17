from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.message_bus import messages
from infrahub.worker import WORKER_IDENTITY

from .registry import refresh_branches

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices


async def trigger_branch_refresh(service: InfrahubServices) -> None:
    service.log.debug("Running branch refresh task")
    async with service.database.start_session() as db:
        await refresh_branches(db=db)

    await service.component.refresh_schema_hash()


async def push_telemetry(service: InfrahubServices) -> None:
    if await service.component.is_primary_api():
        service.log.debug(f"Primary identity matches my identity={WORKER_IDENTITY}. Pushing usage telemetry.")
        message = messages.SendTelemetryPush()
        await service.send(message=message)
