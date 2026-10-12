from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreNumberPool
from infrahub.pools.scope import AllocationScope

if TYPE_CHECKING:
    from collections.abc import Iterable

    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class ScopedNumberPool:
    """A number pool whose space is divided by an allocation scope."""

    id: str
    name: str
    kind: str
    tracked_attribute: str
    scope: AllocationScope


class ScopedNumberPoolReader:
    """Reads the number pools attached to some kinds that carry an allocation scope."""

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
        pools = await NodeManager.query(
            db=self.db, schema=CoreNumberPool, filters={"allocation_scope__isnull": False}, branch_agnostic=True
        )
        return self._scoped(pools=pools)

    def _scoped(self, pools: Iterable[CoreNumberPool]) -> list[ScopedNumberPool]:
        scoped_pools: list[ScopedNumberPool] = []
        for pool in pools:
            scope = AllocationScope.from_stored(value=pool.allocation_scope.value, pool=pool.name.value)
            if scope.is_empty:
                continue
            scoped_pools.append(
                ScopedNumberPool(
                    id=pool.get_id(),
                    name=pool.name.value,
                    kind=pool.node.value,
                    tracked_attribute=pool.node_attribute.value,
                    scope=scope,
                )
            )
        return scoped_pools
