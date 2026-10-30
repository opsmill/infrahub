from __future__ import annotations

from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import TYPE_CHECKING, Protocol

from infrahub import lock
from infrahub.exceptions import LockWaitTimeoutError, ValidationError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub.database import InfrahubDatabase

RESOURCE_POOL_LOCK_NAMESPACE = "resource_pool"


class NumberPoolLocker(Protocol):
    def changing(self, pool_id: str, pool_name: str) -> AbstractAsyncContextManager[None]:
        """Hold the pool alone while its ranges change, once every write reading them has committed.

        Raises:
            ValidationError: When writes still read the ranges once the wait limit passes.

        """
        ...


class NumberPoolLock:
    """Lock a number pool so that a change to its ranges runs alone."""

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

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
