from __future__ import annotations

from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import TYPE_CHECKING, Protocol

from infrahub import lock
from infrahub.exceptions import LockWaitTimeoutError, ValidationError
from infrahub.pools.scope import AllocationScope

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.scope import Division

RESOURCE_POOL_LOCK_NAMESPACE = "resource_pool"
UNSCOPED_PICKING_KEY = "all"


class NumberPoolLocker(Protocol):
    def changing(self, pool_id: str, pool_name: str) -> AbstractAsyncContextManager[None]:
        """Hold the pool alone while its ranges change, once every write reading them has committed.

        Raises:
            ValidationError: When writes still read the ranges once the wait limit passes.

        """
        ...

    def holding(self, pool_id: str) -> AbstractAsyncContextManager[None]:
        """Keep the pool's ranges from changing until the write reading them commits, alongside other such writes."""
        ...

    def picking(self, pool: Node, division: Division | None) -> AbstractAsyncContextManager[None]:
        """Keep a second allocation in the same division, or in the whole pool without a scope, from picking at once.

        Raises:
            ValidationError: When a division is given to a pool that has no allocation scope.

        """
        ...


class NumberPoolLock:
    """Lock a number pool so that a change to its ranges and the writes checking numbers against them run apart.

    The pool lock is exclusive for a range change and shared by the writes, so writes in different divisions
    still run in parallel; a write keeps its share until its transaction ends, since the number it checked
    is only visible to a range change once committed.
    """

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    @staticmethod
    def picking_lock_name(pool_id: str, division_key: str | None) -> str:
        """Return the name of the lock that allocations from the same pool and division take to pick a number."""
        return f"{RESOURCE_POOL_LOCK_NAMESPACE}.{pool_id}.{division_key or UNSCOPED_PICKING_KEY}"

    @asynccontextmanager
    async def changing(self, pool_id: str, pool_name: str) -> AsyncGenerator[None]:
        pool_lock = lock.registry.get_shared(name=pool_id, namespace=RESOURCE_POOL_LOCK_NAMESPACE)
        try:
            await pool_lock.acquire_exclusive()
        except LockWaitTimeoutError as exc:
            raise ValidationError(
                input_value=f"Numbers are still being allocated from the pool {pool_name}; retry the change."
            ) from exc
        try:
            yield
        finally:
            await pool_lock.release_exclusive()

    @asynccontextmanager
    async def holding(self, pool_id: str) -> AsyncGenerator[None]:
        shared = lock.registry.get_shared(name=pool_id, namespace=RESOURCE_POOL_LOCK_NAMESPACE).shared()
        if self.db.can_hold_until_transaction_end:
            await self.db.hold_until_transaction_end(shared)
            yield
            return
        async with shared:
            yield

    def picking(self, pool: Node, division: Division | None) -> AbstractAsyncContextManager[None]:
        if division is None:
            return lock.registry.get(name=self.picking_lock_name(pool_id=pool.get_id(), division_key=None))
        scope = AllocationScope.from_stored(value=pool.get_attribute("allocation_scope").value, pool=pool.get_id())
        if scope.is_empty:
            raise ValidationError(f"The pool {pool.get_id()} has no allocation scope; a division cannot be applied")
        return lock.registry.get(name=self.picking_lock_name(pool_id=pool.get_id(), division_key=division.key))
