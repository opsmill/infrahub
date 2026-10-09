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
    """A number pool whose space is divided by an allocation scope."""

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
class KindNumberPools:
    """The scoped pools attached to some kinds, and the pools of those kinds whose stored scope cannot be read."""

    scoped: list[ScopedNumberPool]
    unreadable: list[UnreadableScopeNumberPool]


class ScopedNumberPoolReader:
    """Reads the number pools attached to some kinds that carry an allocation scope."""

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def get_for_kinds(self, kinds: Iterable[str]) -> KindNumberPools:
        """Return the scoped pools attached to any of the kinds, apart from the pools whose stored scope cannot be read."""
        pools = await NodeManager.query(db=self.db, schema=CoreNumberPool, filters={"node__values": sorted(set(kinds))})
        scoped_pools: list[ScopedNumberPool] = []
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
        return KindNumberPools(scoped=scoped_pools, unreadable=unreadable_pools)
