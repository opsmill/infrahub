from __future__ import annotations

from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import TYPE_CHECKING, Protocol

from infrahub import lock
from infrahub.exceptions import LockWaitTimeoutError, ValidationError
from infrahub.log import get_logger
from infrahub.pools.scope import AllocationScope

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub.core.node import Node
    from infrahub.core.protocols import CoreNumberPool
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.scope import Division

log = get_logger()

RESOURCE_POOL_LOCK_NAMESPACE = "resource_pool"
UNSCOPED_PICKING_KEY = "all"


def picking_lock_name(pool_id: str, division_key: str | None) -> str:
    """Return the name of the lock that allocations from the same pool and division take to pick a number."""
    return f"{RESOURCE_POOL_LOCK_NAMESPACE}.{pool_id}.{division_key or UNSCOPED_PICKING_KEY}"


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

    def picking(self, pool: Node | CoreNumberPool, division: Division | None) -> AbstractAsyncContextManager[None]:
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
        """Keep the writes' shares of a pool on `db` until the transaction open on it ends, when there is one."""
        self.db = db

    def _pool_lock(self, pool_id: str) -> lock.InfrahubSharedLock:
        """Return the pool's lock, which a range change takes exclusively and the writes reading the ranges share."""
        return lock.registry.get_shared(name=pool_id, namespace=RESOURCE_POOL_LOCK_NAMESPACE)

    @asynccontextmanager
    async def changing(self, pool_id: str, pool_name: str) -> AsyncGenerator[None]:
        """Hold the pool alone while its ranges change, once every write reading them has committed.

        Raises:
            ValidationError: When writes still read the ranges once the wait limit passes.

        """
        pool_lock = self._pool_lock(pool_id=pool_id)
        try:
            await pool_lock.acquire_exclusive()
        except LockWaitTimeoutError as exc:
            log.warning(exc.message, pool_id=pool_id)
            raise ValidationError(
                input_value=f"Numbers are still being allocated from the pool {pool_name}; retry the change."
            ) from exc
        try:
            yield
        finally:
            await pool_lock.release_exclusive()

    @asynccontextmanager
    async def holding(self, pool_id: str) -> AsyncGenerator[None]:
        """Keep the pool's ranges from changing until the write reading them commits, alongside other such writes.

        Inside a transaction the share is kept until the transaction commits or rolls back, not until the block ends.
        """
        shared = self._pool_lock(pool_id=pool_id).shared()
        if self.db.can_hold_until_transaction_end:
            await self.db.hold_until_transaction_end(shared)
            yield
            return
        async with shared:
            yield

    def picking(self, pool: Node | CoreNumberPool, division: Division | None) -> AbstractAsyncContextManager[None]:
        """Keep a second allocation in the same division, or in the whole pool without a scope, from picking at once.

        Raises:
            ValidationError: When a division is given to a pool that has no allocation scope.

        """
        division_key = None
        if division is not None:
            scope = AllocationScope.from_stored(value=pool.get_attribute("allocation_scope").value, pool=pool.get_id())
            if scope.is_empty:
                raise ValidationError(f"The pool {pool.get_id()} has no allocation scope; a division cannot be applied")
            division_key = division.key
        return lock.registry.get(name=picking_lock_name(pool_id=pool.get_id(), division_key=division_key))
