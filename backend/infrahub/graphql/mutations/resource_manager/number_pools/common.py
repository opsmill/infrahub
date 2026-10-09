from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import lock
from infrahub.core.constants import InfrahubKind, NumberPoolType
from infrahub.core.manager import NodeManager
from infrahub.core.node.lock_utils import RESOURCE_POOL_LOCK_NAMESPACE
from infrahub.exceptions import ValidationError
from infrahub.pools.number_pool_range_validation import NumberRangeBounds
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.number_pool_shorthand import NumberPoolShorthandMirror

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.node import Node
    from infrahub.core.protocols import CoreNumberPoolRange
    from infrahub.database import InfrahubDatabase


SCHEMA_POOL_EDIT_HINT = "update the schema in the default branch instead"
SCHEMA_POOL_SHORTHAND_REFUSED = (
    f"start_range or end_range can't be updated on schema defined pools, {SCHEMA_POOL_EDIT_HINT}"
)
SCHEMA_POOL_RANGES_REFUSED = f"ranges can't be updated on schema defined pools, {SCHEMA_POOL_EDIT_HINT}"


def refuse_schema_pool(pool: Node, message: str) -> None:
    if pool.get_attribute("pool_type").get_value() == NumberPoolType.SCHEMA.value:
        raise ValidationError(input_value=message)


def pool_lock(pool_id: str) -> lock.InfrahubLock:
    return lock.registry.get(name=pool_id, namespace=RESOURCE_POOL_LOCK_NAMESPACE)


def range_bounds(ranges: Sequence[CoreNumberPoolRange]) -> list[NumberRangeBounds]:
    return [
        NumberRangeBounds(start=int(pool_range.start.value), end=int(pool_range.end.value), id=pool_range.get_id())
        for pool_range in ranges
    ]


async def sync_shorthand(
    db: InfrahubDatabase, pool_id: str, ranges: Sequence[CoreNumberPoolRange], user_id: str
) -> Node:
    """Mirror the ranges into the pool's shorthand and return the pool as stored afterwards."""
    # Loaded here so the mirror's no-op check compares against the stored shorthand.
    pool = await NodeManager.get_one(db=db, id=pool_id, kind=InfrahubKind.NUMBERPOOL, raise_on_error=True)
    await NumberPoolShorthandMirror(repository=NumberPoolRepository(db=db)).sync(
        pool=pool, ranges=ranges, user_id=user_id
    )
    return pool
