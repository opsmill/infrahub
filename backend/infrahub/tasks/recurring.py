from __future__ import annotations

from typing import TYPE_CHECKING

from .registry import refresh_branches

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices


async def trigger_branch_refresh(service: InfrahubServices) -> None:
    service.log.info("Running branch refresh task")
    async with service.database.start_session() as db:
        await refresh_branches(db=db)
