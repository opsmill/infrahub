from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreNumberPool
from infrahub.exceptions import ValidationError
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


@dataclass(frozen=True)
class UnreadableScopeNumberPool:
    """A number pool whose stored allocation scope is not a list of elements, kept as stored."""

    id: str
    name: str
    kind: str
    tracked_attribute: str
    stored_scope: object
    reason: str


@dataclass(frozen=True)
class NumberPoolScopes:
    """Pools read with their allocation scope, apart from the pools whose stored scope cannot be read."""

    readable: list[ScopedNumberPool]
    unreadable: list[UnreadableScopeNumberPool]


class ScopedNumberPoolReader:
    """Reads number pools with the allocation scope that divides their space."""

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def get_for_kinds(self, kinds: Iterable[str]) -> NumberPoolScopes:
        """Return the scoped pools attached to any of the kinds, apart from the pools whose stored scope cannot be read."""
        pools = await NodeManager.query(db=self.db, schema=CoreNumberPool, filters={"node__values": sorted(set(kinds))})
        read = self._read(pools=pools)
        return NumberPoolScopes(
            readable=[pool for pool in read.readable if not pool.scope.is_empty], unreadable=read.unreadable
        )

    async def get_by_ids(self, ids: Iterable[str]) -> NumberPoolScopes:
        """Return the pools with these ids, unscoped ones included, apart from the pools whose stored scope cannot be read."""
        pools = await NodeManager.query(db=self.db, schema=CoreNumberPool, filters={"ids": sorted(set(ids))})
        return self._read(pools=pools)

    @staticmethod
    def _read(pools: list[CoreNumberPool]) -> NumberPoolScopes:
        readable_pools: list[ScopedNumberPool] = []
        unreadable_pools: list[UnreadableScopeNumberPool] = []
        for pool in pools:
            stored_scope = pool.allocation_scope.value
            try:
                scope = AllocationScope.from_stored(value=stored_scope, pool=pool.name.value)
            except ValidationError as exc:
                unreadable_pools.append(
                    UnreadableScopeNumberPool(
                        id=pool.get_id(),
                        name=pool.name.value,
                        kind=pool.node.value,
                        tracked_attribute=pool.node_attribute.value,
                        stored_scope=stored_scope,
                        reason=exc.message,
                    )
                )
                continue
            readable_pools.append(
                ScopedNumberPool(
                    id=pool.get_id(),
                    name=pool.name.value,
                    kind=pool.node.value,
                    tracked_attribute=pool.node_attribute.value,
                    scope=scope,
                )
            )
        return NumberPoolScopes(readable=readable_pools, unreadable=unreadable_pools)
