from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.constants import NumberPoolType
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreNumberPool
from infrahub.pools.scope import AllocationScope

if TYPE_CHECKING:
    from collections.abc import Iterable

    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class ScopedNumberPool:
    """A number pool and the allocation scope that divides its space, empty when the pool is unscoped."""

    id: str
    name: str
    kind: str
    tracked_attribute: str
    scope: AllocationScope


class ScopedNumberPoolReader:
    """Reads number pools with the allocation scope that divides their space."""

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def get_for_kinds(self, kinds: Iterable[str]) -> list[ScopedNumberPool]:
        """Return the scoped pools attached to any of the kinds.

        Raises:
            ValidationError: When a pool stores an allocation scope that is not a list of elements.

        """
        pools = await NodeManager.query(db=self.db, schema=CoreNumberPool, filters={"node__values": sorted(set(kinds))})
        return self._scoped(pools=pools)

    async def get_with_scope(self) -> list[ScopedNumberPool]:
        """Return every pool that stores a scope.

        Raises:
            ValidationError: When a pool stores an allocation scope that is not a list of elements.

        """
        # An `isnull` filter on a List attribute matches no node, so the unscoped pools are dropped after the read.
        pools = await NodeManager.query(db=self.db, schema=CoreNumberPool, branch_agnostic=True)
        return self._scoped(pools=pools)

    async def get_schema_pool_ids(self, attributes: Iterable[tuple[str, str]]) -> dict[tuple[str, str], str]:
        """Return the id of the pool the schema created for each (kind, attribute) pair that has one."""
        requested = set(attributes)
        pools = await NodeManager.query(
            db=self.db,
            schema=CoreNumberPool,
            filters={
                "node__values": sorted({kind for kind, _ in requested}),
                "pool_type__value": NumberPoolType.SCHEMA.value,
            },
            branch_agnostic=True,
        )
        return {
            (pool.node.value, pool.node_attribute.value): pool.get_id()
            for pool in pools
            if (pool.node.value, pool.node_attribute.value) in requested
        }

    async def get_by_ids(self, ids: Iterable[str]) -> list[ScopedNumberPool]:
        """Return the pools with these ids, unscoped ones included.

        Raises:
            ValidationError: When a pool stores an allocation scope that is not a list of elements.

        """
        pools = await NodeManager.query(db=self.db, schema=CoreNumberPool, filters={"ids": sorted(set(ids))})
        return self._read(pools=pools)

    def _scoped(self, pools: Iterable[CoreNumberPool]) -> list[ScopedNumberPool]:
        return [pool for pool in self._read(pools=pools) if not pool.scope.is_empty]

    @staticmethod
    def _read(pools: Iterable[CoreNumberPool]) -> list[ScopedNumberPool]:
        read_pools: list[ScopedNumberPool] = []
        for pool in pools:
            scope = AllocationScope.from_stored(value=pool.allocation_scope.value, pool=pool.name.value)
            read_pools.append(
                ScopedNumberPool(
                    id=pool.get_id(),
                    name=pool.name.value,
                    kind=pool.node.value,
                    tracked_attribute=pool.node_attribute.value,
                    scope=scope,
                )
            )
        return read_pools
