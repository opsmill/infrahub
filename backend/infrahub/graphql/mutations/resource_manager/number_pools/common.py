from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from infrahub import lock
from infrahub.core.manager import NodeManager
from infrahub.core.node.lock_utils import RESOURCE_POOL_LOCK_NAMESPACE
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.pools.number_pool_range_validation import NumberRangeBounds
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.number_pool_shorthand import NumberPoolShorthandMirror

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from infrahub.core.protocols import CoreNumberPoolRange
    from infrahub.database import InfrahubDatabase


@asynccontextmanager
async def within_transaction(db: InfrahubDatabase) -> AsyncIterator[InfrahubDatabase]:
    if db.is_transaction:
        yield db
        return
    async with db.start_transaction() as dbt:
        yield dbt


def pool_lock(pool_id: str) -> lock.InfrahubLock:
    return lock.registry.get(name=pool_id, namespace=RESOURCE_POOL_LOCK_NAMESPACE)


def range_bounds(ranges: Sequence[CoreNumberPoolRange]) -> list[NumberRangeBounds]:
    return [
        NumberRangeBounds(start=int(pool_range.start.value), end=int(pool_range.end.value), id=pool_range.get_id())
        for pool_range in ranges
    ]


async def sync_shorthand(
    db: InfrahubDatabase, pool_id: str, ranges: Sequence[CoreNumberPoolRange], user_id: str
) -> None:
    # Loaded here so the mirror's no-op check compares against the stored shorthand.
    pool = await NodeManager.get_one_by_id_or_default_filter(db=db, id=pool_id, kind=CoreNumberPool)
    await NumberPoolShorthandMirror(db=db, repository=NumberPoolRepository(db=db)).sync(
        pool=pool, ranges=ranges, user_id=user_id
    )
