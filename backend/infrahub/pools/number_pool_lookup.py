from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol

from infrahub_sdk.utils import is_valid_uuid

from infrahub.core.constants import InfrahubKind
from infrahub.core.protocols import CoreNumberPool, CoreNumberPoolRange
from infrahub.core.query.resource_manager import NumberPoolGetTrackingPool
from infrahub.exceptions import NodeNotFoundError
from infrahub.pools.number_pool_space import to_pool_ranges

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.number_ranges import PoolRange


class NumberPoolReader(Protocol):
    """Reads number pools by id, or by filters on their attributes."""

    async def get_one(
        self, id: str, db: InfrahubDatabase, kind: type[CoreNumberPool], raise_on_error: Literal[True]
    ) -> CoreNumberPool: ...

    async def query(
        self, db: InfrahubDatabase, schema: type[CoreNumberPool], filters: dict | None
    ) -> Sequence[CoreNumberPool]: ...


class NumberPoolLookup:
    """Find the number pool a write names, by its id or by its name."""

    def __init__(self, db: InfrahubDatabase, node_manager: NumberPoolReader) -> None:
        self.db = db
        self.node_manager = node_manager

    async def find(self, pool_ref: str) -> CoreNumberPool:
        """Return the number pool whose id or name is `pool_ref`.

        Raises:
            NodeNotFoundError: When no number pool has that id or name.

        """
        if is_valid_uuid(pool_ref):
            return await self.node_manager.get_one(id=pool_ref, db=self.db, kind=CoreNumberPool, raise_on_error=True)
        results = await self.node_manager.query(db=self.db, schema=CoreNumberPool, filters={"name__value": pool_ref})
        if not results:
            raise NodeNotFoundError(node_type=InfrahubKind.NUMBERPOOL, identifier=pool_ref)
        return results[0]

    async def get_tracking_pool_id(self, attribute_id: str) -> str | None:
        """Return the id of the number pool currently tracking the attribute, or None when none does."""
        query = await NumberPoolGetTrackingPool.init(db=self.db, attribute_id=attribute_id)
        await query.execute(db=self.db)
        return query.get_pool_id()


class NumberPoolRangeNodeReader(Protocol):
    """Reads the range nodes of number pools, on every branch at once."""

    async def query(
        self,
        db: InfrahubDatabase,
        schema: type[CoreNumberPoolRange],
        filters: dict | None,
        *,
        at: Timestamp | str | None,
        branch_agnostic: bool,
    ) -> Sequence[CoreNumberPoolRange]: ...


class NumberPoolRangeLookup:
    """Read the ranges of a number pool."""

    def __init__(self, db: InfrahubDatabase, node_manager: NumberPoolRangeNodeReader) -> None:
        self.db = db
        self.node_manager = node_manager

    async def get_ranges(self, pool_id: str, at: Timestamp | str | None = None) -> list[CoreNumberPoolRange]:
        """Return the ranges a pool allocates from, lowest start first."""
        pool_ranges = await self.node_manager.query(
            db=self.db, schema=CoreNumberPoolRange, filters={"pool__ids": [pool_id]}, at=at, branch_agnostic=True
        )
        return sorted(pool_ranges, key=lambda pool_range: int(pool_range.start.value))

    async def get_pool_ranges(self, pool_id: str, at: Timestamp | str | None = None) -> list[PoolRange]:
        """Return the pool's ranges as plain start, end, weight and id values, lowest start first."""
        return to_pool_ranges(ranges=await self.get_ranges(pool_id=pool_id, at=at))
