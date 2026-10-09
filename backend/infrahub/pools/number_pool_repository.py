from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from infrahub.core.constants import SYSTEM_USER_ID, InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreNumberPoolRange
from infrahub.core.query.resource_manager import (
    NumberPoolGetFree,
    NumberPoolGetReserved,
    NumberPoolGetTaken,
    NumberPoolGetUsed,
    NumberPoolReleaseAllReserved,
    NumberPoolSetReserved,
)
from infrahub.core.timestamp import Timestamp
from infrahub.database import within_transaction
from infrahub.pools.number_pool_space import to_pool_ranges

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.number_ranges import EffectiveSpace, PoolRange


class NumberPoolRangeStore(Protocol):
    """Reads and writes the ranges a number pool allocates from, and the shorthand that mirrors them."""

    async def get_ranges(self, pool_id: str, at: Timestamp | None = None) -> list[CoreNumberPoolRange]: ...

    async def save_shorthand(
        self, pool: Node, start: int | None, end: int | None, at: Timestamp | None = None, user_id: str = SYSTEM_USER_ID
    ) -> None: ...

    async def create_range(
        self,
        pool: Node,
        start: int,
        end: int,
        weight: int | None = None,
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
    ) -> CoreNumberPoolRange: ...

    async def save_range(
        self,
        pool_range: CoreNumberPoolRange,
        start: int,
        end: int,
        weight: int | None,
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
    ) -> None: ...

    async def delete_range(
        self, pool_range: CoreNumberPoolRange, at: Timestamp | None = None, user_id: str = SYSTEM_USER_ID
    ) -> None: ...

    async def delete_pool(
        self, pool_id: str, at: Timestamp | None = None, user_id: str = SYSTEM_USER_ID
    ) -> list[Node]: ...


class NumberPoolRangeStoreFactory(Protocol):
    """Builds a range store writing through the given database."""

    def __call__(self, db: InfrahubDatabase) -> NumberPoolRangeStore: ...


class NumberPoolRepository(NumberPoolRangeStore):
    """Database access for number pools: the ranges they allocate from and the numbers they account for."""

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def get_ranges(self, pool_id: str, at: Timestamp | str | None = None) -> list[CoreNumberPoolRange]:
        """Return the ranges a pool allocates from, lowest start first."""
        pool_ranges = await NodeManager.query(
            db=self.db,
            schema=CoreNumberPoolRange,
            filters={"pool__ids": [pool_id]},
            at=at,
            branch_agnostic=True,
        )
        return sorted(pool_ranges, key=lambda pool_range: int(pool_range.start.value))

    async def get_pool_ranges(self, pool_id: str, at: Timestamp | str | None = None) -> list[PoolRange]:
        """Return the pool's ranges as plain start, end, weight and id values, lowest start first."""
        return to_pool_ranges(ranges=await self.get_ranges(pool_id=pool_id, at=at))

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

    async def save_shorthand(
        self, pool: Node, start: int | None, end: int | None, at: Timestamp | None = None, user_id: str = SYSTEM_USER_ID
    ) -> None:
        """Write the pool's start and end bounds, leaving any other pending change on the node unsaved."""
        pool.get_attribute("start_range").value = start
        pool.get_attribute("end_range").value = end
        await pool.save(db=self.db, at=at, user_id=user_id, fields=["start_range", "end_range"])

    async def get_used(self, pool: CoreNumberPool, branch: Branch, space: EffectiveSpace) -> list[int]:
        """Return the numbers inside `space` the pool currently accounts for."""
        if space.is_empty:
            return []
        query = await NumberPoolGetUsed.init(
            db=self.db, branch=branch, pool=pool, ranges=space.as_query_ranges(), branch_agnostic=True
        )
        await query.execute(db=self.db)
        used = [result.value for result in query.iter_results()]
        return [item for item in used if item is not None]

    async def get_free(self, pool: CoreNumberPool, branch: Branch, min_value: int, max_value: int) -> int | None:
        """Return the lowest number in `[min_value, max_value]` the pool does not account for, or None."""
        query = await NumberPoolGetFree.init(
            db=self.db, branch=branch, pool=pool, branch_agnostic=True, min_value=min_value, max_value=max_value
        )
        await query.execute(db=self.db)
        return query.get_result_value()

    async def get_taken(self, pool: CoreNumberPool, branch: Branch, space: EffectiveSpace) -> set[int]:
        """Return the values inside `space` already held by the pool's attribute on its target kind."""
        if space.is_empty:
            return set()
        query = await NumberPoolGetTaken.init(db=self.db, branch=branch, pool=pool, ranges=space.as_query_ranges())
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
        allocated_value: int | None,
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
    ) -> None:
        """Record that the pool accounts for the attribute, whatever value it holds.

        `allocated_value` is the number the pool allocated in this write, or None when the pool only tracks a
        number the attribute already holds.
        """
        query = await NumberPoolSetReserved.init(
            db=self.db,
            pool_id=pool_id,
            identifier=identifier,
            attribute_id=attribute_id,
            allocated_value=allocated_value,
            at=at,
            user_id=user_id,
        )
        await query.execute(db=self.db)

    async def delete_pool(self, pool_id: str, at: Timestamp | None = None, user_id: str = SYSTEM_USER_ID) -> list[Node]:
        """Delete the pool with its ranges and end every record it holds, so each number stays on its object.

        Returns:
            The pool and the nodes deleted along with it, empty when no such pool exists.

        """
        delete_at = Timestamp(at)
        async with within_transaction(db=self.db) as dbt:
            pool = await NodeManager.get_one(db=dbt, id=pool_id, kind=InfrahubKind.NUMBERPOOL, branch_agnostic=True)
            if pool is None:
                return []
            release = await NumberPoolReleaseAllReserved.init(db=dbt, pool_id=pool_id, at=delete_at, user_id=user_id)
            await release.execute(db=dbt)
            return await NodeManager.delete(db=dbt, nodes=[pool], at=delete_at, user_id=user_id)
