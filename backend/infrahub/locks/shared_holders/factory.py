from __future__ import annotations

from typing import TYPE_CHECKING

from .local import LocalSharedHolderStore
from .redis import RedisSharedHolderStore

if TYPE_CHECKING:
    import redis.asyncio as redis

    from .interface import SharedHolderStore


def build_shared_holder_store(connection: redis.Redis | None) -> SharedHolderStore:
    """Return a store on the Redis server `connection` reaches, or one in this process when there is no connection."""
    if connection is not None:
        return RedisSharedHolderStore(connection=connection)
    return LocalSharedHolderStore()
