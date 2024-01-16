from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from infrahub.message_bus import messages
from infrahub.worker import WORKER_IDENTITY

from .registry import refresh_branches

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices


async def trigger_branch_refresh(service: InfrahubServices, expiration: Optional[int] = None) -> None:  # pylint: disable=unused-argument
    service.log.debug("Running branch refresh task")
    async with service.database.start_session() as db:
        await refresh_branches(db=db)


async def resync_repositories(service: InfrahubServices, expiration: Optional[int] = None) -> None:
    primary_identity = await service.cache.get("primary_api_server_id")
    if primary_identity == WORKER_IDENTITY:
        service.log.debug(
            f"Primary identity={primary_identity} matches my identity={WORKER_IDENTITY}. Posting sync of repo message."
        )
        message = messages.RequestGitSync()
        if expiration is not None:
            message.assign_expiration(expiration)
        await service.send(message=message)
