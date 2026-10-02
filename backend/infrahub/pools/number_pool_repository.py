from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreNumberPoolRange
from infrahub.core.query.resource_manager import (
    NumberPoolGetFree,
    NumberPoolGetReserved,
    NumberPoolGetTaken,
    NumberPoolGetUsed,
    NumberPoolSetReserved,
    PoolRecordProvenance,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class NumberPoolRangeStore(Protocol):
    """Reads and writes the ranges a number pool allocates from."""

    async def get_ranges(self, pool_id: str, at: Timestamp | None = None) -> list[CoreNumberPoolRange]: ...

    async def create_range(
        self,
        pool: Node,
        start: int,
        end: int,
        weight: int | None = None,
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
    ) -> CoreNumberPoolRange: ...


class NumberPoolRangeStoreFactory(Protocol):
    """Builds a range store writing through the given database."""

    def __call__(self, db: InfrahubDatabase) -> NumberPoolRangeStore: ...


class NumberPoolRepository(NumberPoolRangeStore):
    """Database access for number pools: the ranges they allocate from and the numbers they account for."""

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def get_ranges(self, pool_id: str, at: Timestamp | None = None) -> list[CoreNumberPoolRange]:
        """Return the ranges a pool allocates from, lowest start first."""
        pool_ranges = await NodeManager.query(
            db=self.db,
            schema=CoreNumberPoolRange,
            filters={"pool__ids": [pool_id]},
            at=at,
            branch_agnostic=True,
        )
        return sorted(pool_ranges, key=lambda pool_range: int(pool_range.start.value))

    async def create_range(
        self,
        pool: Node,
        start: int,
        end: int,
        weight: int | None = None,
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
    ) -> CoreNumberPoolRange:
        """Add a range to the pool."""
        pool_range = await Node.init(db=self.db, schema=CoreNumberPoolRange)
        await pool_range.new(db=self.db, start=start, end=end, allocation_weight=weight, pool=pool)
        await pool_range.save(db=self.db, at=at, user_id=user_id)
        return pool_range

    async def save_range_bounds(
        self,
        pool_range: CoreNumberPoolRange,
        start: int,
        end: int,
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
    ) -> None:
        """Rewrite a range's bounds in place, keeping its identity and weight."""
        pool_range.start.value = start
        pool_range.end.value = end
        await pool_range.save(db=self.db, at=at, user_id=user_id)

    async def save_range(
        self,
        pool_range: CoreNumberPoolRange,
        start: int,
        end: int,
        weight: int | None,
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
    ) -> None:
        """Rewrite a range's bounds and weight in place, keeping its identity."""
        pool_range.start.value = start
        pool_range.end.value = end
        pool_range.allocation_weight.value = weight
        await pool_range.save(db=self.db, at=at, user_id=user_id)

    async def delete_range(
        self, pool_range: CoreNumberPoolRange, at: Timestamp | None = None, user_id: str = SYSTEM_USER_ID
    ) -> None:
        """Remove a range from its pool."""
        await pool_range.delete(db=self.db, at=at, user_id=user_id)

    async def get_used(self, pool: CoreNumberPool, branch: Branch) -> list[int]:
        """Return the numbers the pool currently accounts for."""
        query = await NumberPoolGetUsed.init(db=self.db, branch=branch, pool=pool, branch_agnostic=True)
        await query.execute(db=self.db)
        used = [result.value for result in query.iter_results()]
        return [item for item in used if item is not None]

    async def get_free(
        self, pool: CoreNumberPool, branch: Branch, min_value: int | None = None, max_value: int | None = None
    ) -> int | None:
        """Return the lowest number in `[min_value, max_value]` the pool does not account for, or None."""
        query = await NumberPoolGetFree.init(
            db=self.db, branch=branch, pool=pool, branch_agnostic=True, min_value=min_value, max_value=max_value
        )
        await query.execute(db=self.db)
        return query.get_result_value()

    async def get_taken(
        self, pool: CoreNumberPool, branch: Branch, min_value: int | None = None, max_value: int | None = None
    ) -> set[int]:
        """Return the values already held by the pool's attribute on its target kind, within range."""
        query = await NumberPoolGetTaken.init(
            db=self.db, branch=branch, pool=pool, min_value=min_value, max_value=max_value
        )
        await query.execute(db=self.db)
        return query.get_taken_values()

    async def get_reservation(self, pool_id: str, branch: Branch, identifier: str) -> int | None:
        """Return the number the pool reserved for `identifier`, or None when it holds no reservation."""
        query = await NumberPoolGetReserved.init(db=self.db, branch=branch, pool_id=pool_id, identifier=identifier)
        await query.execute(db=self.db)
        return query.get_reservation()

    async def reserve(
        self,
        pool_id: str,
        identifier: str,
        attribute_id: str,
        provenance: PoolRecordProvenance,
        at: Timestamp | None = None,
    ) -> None:
        """Record that the pool accounts for the attribute, whatever value it holds."""
        query = await NumberPoolSetReserved.init(
            db=self.db,
            pool_id=pool_id,
            identifier=identifier,
            attribute_id=attribute_id,
            provenance=provenance,
            at=at,
        )
        await query.execute(db=self.db)
