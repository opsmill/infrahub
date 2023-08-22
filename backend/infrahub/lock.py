from __future__ import annotations

import uuid
from asyncio import Lock as LocalLock
from asyncio import sleep
from typing import TYPE_CHECKING, Dict, List, Optional, Type

import redis.asyncio as redis
from redis.asyncio.lock import Lock as GlobalLock

from infrahub import config

if TYPE_CHECKING:
    from types import TracebackType

registry: InfrahubLockRegistry = None


LOCAL_SCHEMA_LOCK = "local.schema"
GLOBAL_SCHEMA_LOCK = "global.schema"
GLOBAL_GRAPH_LOCK = "global.graph"


class InfrahubMultiLock:
    """Context manager to allow multiple locks to be reserved together"""

    def __init__(self, _registry: InfrahubLockRegistry, locks: Optional[List[str]] = None):
        self.registry = _registry
        self.locks = locks or []

    async def __aenter__(self):
        await self.acquire()

    async def __aexit__(self, exc_type: Type[BaseException], exc_value: BaseException, traceback: TracebackType):
        await self.release()

    async def acquire(self) -> None:
        for lock in self.locks:
            await self.registry.get(lock).acquire()

    async def release(self) -> None:
        for lock in reversed(self.locks):
            await self.registry.get(lock).release()


class InfrahubLock:
    """InfrahubLock object to provide a unified interface for both Local and Distributed locks.

    Having the same interface for both local and distributed tests will simplify our unit tests.
    """

    def __init__(self, name: str, connection: Optional[redis.Redis] = None, local: Optional[bool] = None):
        self.use_local = local
        self.local: LocalLock = None
        self.remote: GlobalLock = None
        self.name = name
        self.connection = connection

        if not self.connection or (self.use_local is None and name.startswith("local.")):
            self.use_local = True

        if self.use_local:
            self.local = LocalLock()
        else:
            self.remote = GlobalLock(redis=self.connection, name=self.name)

    async def __aenter__(self):
        await self.acquire()

    async def __aexit__(self, exc_type: Type[BaseException], exc_value: BaseException, traceback: TracebackType):
        await self.release()

    async def acquire(self) -> None:
        if not self.use_local:
            await self.remote.acquire()
        else:
            await self.local.acquire()

    async def release(self) -> None:
        if not self.use_local:
            await self.remote.release()
        else:
            self.local.release()

    async def locked(self) -> bool:
        if not self.use_local:
            return await self.remote.locked()

        return self.local.locked()


class InfrahubLockRegistry:
    def __init__(self, token: Optional[str] = None, local_only: bool = False):
        if local_only:
            self.connection = None
        else:
            self.connection = redis.Redis(
                host=config.SETTINGS.cache.address,
                port=config.SETTINGS.cache.service_port,
                db=config.SETTINGS.cache.database,
            )

        self.token = token or str(uuid.uuid4())
        self.locks: Dict[str, InfrahubLock] = {}

    def get(self, name: str) -> InfrahubLock:
        if name not in self.locks:
            self.locks[name] = InfrahubLock(name=name, connection=self.connection)
        return self.locks[name]

    def local_schema_lock(self) -> LocalLock:
        return self.get(name=LOCAL_SCHEMA_LOCK)

    async def local_schema_wait(self) -> None:
        await self.wait_until_available(name=LOCAL_SCHEMA_LOCK)

    def global_schema_lock(self) -> InfrahubMultiLock:
        return InfrahubMultiLock(_registry=self, locks=[LOCAL_SCHEMA_LOCK, GLOBAL_SCHEMA_LOCK])

    def global_graph_lock(self) -> InfrahubMultiLock:
        return InfrahubMultiLock(_registry=self, locks=[LOCAL_SCHEMA_LOCK, GLOBAL_GRAPH_LOCK, GLOBAL_SCHEMA_LOCK])

    async def wait_until_available(self, name: str) -> None:
        """Wait until a given lock is available.

        This allow to block functions what shouldnt process during an event
        but it's not a blocker if multiple of them happen at the same time.
        """
        while await self.get(name=name).locked():
            await sleep(0.1)


def initialize_lock(local_only: bool = False):
    global registry  # pylint: disable=global-statement
    registry = InfrahubLockRegistry(local_only=local_only)
