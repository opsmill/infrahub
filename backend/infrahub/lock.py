from __future__ import annotations

import asyncio
import time
import uuid
from asyncio import Lock as LocalLock
from asyncio import sleep
from typing import TYPE_CHECKING

import redis.asyncio as redis
from prometheus_client import Histogram
from redis.asyncio.lock import Lock as GlobalLock

from infrahub import config

if TYPE_CHECKING:
    from types import TracebackType

    from infrahub.services import InfrahubServices


registry: InfrahubLockRegistry = None


METRIC_PREFIX = "infrahub_lock"

LOCK_ACQUIRE_TIME_METRICS = Histogram(
    f"{METRIC_PREFIX}_acquire_seconds",
    "Time to acquire the lock on a given object",
    labelnames=["lock", "type"],
    buckets=[0.0005, 0.25, 0.5, 1, 5],
)

LOCK_RESERVE_TIME_METRICS = Histogram(
    f"{METRIC_PREFIX}_reserved_duration_seconds",
    "Time while a given lock is reserved by a given client",
    labelnames=["lock", "type"],
    buckets=[0.001, 0.5, 1, 5, 10],
)

LOCAL_SCHEMA_LOCK = "local.schema"
GLOBAL_INIT_LOCK = "global.init"
GLOBAL_SCHEMA_LOCK = "global.schema"
GLOBAL_GRAPH_LOCK = "global.graph"


class InfrahubMultiLock:
    """Context manager to allow multiple locks to be reserved together"""

    def __init__(self, lock_registry: InfrahubLockRegistry, locks: list[str] | None = None) -> None:
        self.registry = lock_registry
        self.locks = locks or []

    async def __aenter__(self):
        await self.acquire()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ):
        await self.release()

    async def acquire(self) -> None:
        for lock in self.locks:
            await self.registry.get(name=lock).acquire()

    async def release(self) -> None:
        for lock in reversed(self.locks):
            await self.registry.get(name=lock).release()


class NATSLock:
    """Context manager to lock using NATS"""

    def __init__(self, service: InfrahubServices, name: str) -> None:
        self.name = name
        self.token = None
        self.service = service

    async def __aenter__(self):
        await self.acquire()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ):
        await self.release()

    async def acquire(self) -> None:
        token = uuid.uuid1().hex
        while True:
            if await self.do_acquire(token):
                self.token = token
                return True
            await sleep(0.1)  # default Redis GlobalLock value

    async def do_acquire(self, token: str) -> bool:
        return await self.service.cache.set(key=self.name, value=token, not_exists=True)

    async def release(self) -> None:
        await self.service.cache.delete(key=self.name)

    async def locked(self) -> bool:
        return await self.service.cache.get(key=self.name) is not None


class InfrahubLock:
    """InfrahubLock object to provide a unified interface for both Local and Distributed locks.

    Having the same interface for both local and distributed tests will simplify our unit tests.
    """

    def __init__(
        self,
        name: str,
        connection: redis.Redis | InfrahubServices | None = None,
        local: bool | None = None,
        in_multi: bool = False,
    ) -> None:
        self.use_local: bool = local
        self.local: LocalLock = None
        self.remote: GlobalLock = None
        self.name: str = name
        self.connection: redis.Redis | None = connection
        self.in_multi: bool = in_multi
        self.lock_type: str = "multi" if self.in_multi else "individual"
        self.acquire_time: int | None = None
        self.event = asyncio.Event()

        if not self.connection or (self.use_local is None and name.startswith("local.")):
            self.use_local = True

        if self.use_local:
            self.local = LocalLock()
        elif config.SETTINGS.cache.driver == config.CacheDriver.Redis:
            self.remote = GlobalLock(redis=self.connection, name=self.name)
        else:
            self.remote = NATSLock(service=self.connection, name=self.name)

    async def __aenter__(self):
        await self.acquire()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ):
        await self.release()

    async def acquire(self) -> None:
        with LOCK_ACQUIRE_TIME_METRICS.labels(self.name, self.lock_type).time():
            if not self.use_local:
                await self.remote.acquire()
            else:
                await self.local.acquire()
        self.acquire_time = time.time_ns()
        self.event.clear()

    async def release(self) -> None:
        duration_ns = time.time_ns() - self.acquire_time
        LOCK_RESERVE_TIME_METRICS.labels(self.name, self.lock_type).observe(duration_ns / 1000000000)
        if not self.use_local:
            await self.remote.release()
        else:
            self.local.release()
        self.event.set()

    async def locked(self) -> bool:
        if not self.use_local:
            return await self.remote.locked()

        return self.local.locked()


class InfrahubLockRegistry:
    def __init__(
        self, token: str | None = None, local_only: bool = False, service: InfrahubServices | None = None
    ) -> None:
        if config.SETTINGS.cache.enable and not local_only:
            if config.SETTINGS.cache.driver == config.CacheDriver.Redis:
                self.connection = redis.Redis(
                    host=config.SETTINGS.cache.address,
                    port=config.SETTINGS.cache.service_port,
                    db=config.SETTINGS.cache.database,
                    ssl=config.SETTINGS.cache.tls_enabled,
                    ssl_cert_reqs="optional" if not config.SETTINGS.cache.tls_insecure else "none",
                    ssl_check_hostname=not config.SETTINGS.cache.tls_insecure,
                    ssl_ca_certs=config.SETTINGS.cache.tls_ca_file,
                )
            else:
                self.connection = service
        else:
            self.connection = None

        self.token = token or str(uuid.uuid4())
        self.locks: dict[str, InfrahubLock] = {}

    @classmethod
    def _generate_name(cls, name: str, namespace: str | None = None, local: bool | None = None) -> str:
        if namespace is None and local is None:
            return name

        new_name = ""
        if local is True:
            new_name = "local."
        elif local is False:
            new_name = "global."

        if namespace is not None:
            new_name += f"{namespace}."
        new_name += name

        return new_name

    def get_existing(
        self,
        name: str,
        namespace: str | None,
        local: bool | None = None,
    ) -> InfrahubLock | None:
        lock_name = self._generate_name(name=name, namespace=namespace, local=local)
        if lock_name not in self.locks:
            return None
        return self.locks[lock_name]

    def get(
        self, name: str, namespace: str | None = None, local: bool | None = None, in_multi: bool = False
    ) -> InfrahubLock:
        lock_name = self._generate_name(name=name, namespace=namespace, local=local)
        if lock_name not in self.locks:
            self.locks[lock_name] = InfrahubLock(name=lock_name, connection=self.connection, in_multi=in_multi)
        return self.locks[lock_name]

    def local_schema_lock(self) -> LocalLock:
        return self.get(name=LOCAL_SCHEMA_LOCK)

    def initialization(self) -> LocalLock:
        return self.get(name=GLOBAL_INIT_LOCK)

    async def local_schema_wait(self) -> None:
        await self.get(name=LOCAL_SCHEMA_LOCK).event.wait()

    def global_schema_lock(self) -> InfrahubMultiLock:
        return InfrahubMultiLock(lock_registry=self, locks=[LOCAL_SCHEMA_LOCK, GLOBAL_SCHEMA_LOCK])

    def global_graph_lock(self) -> InfrahubMultiLock:
        return InfrahubMultiLock(lock_registry=self, locks=[LOCAL_SCHEMA_LOCK, GLOBAL_GRAPH_LOCK, GLOBAL_SCHEMA_LOCK])


def initialize_lock(local_only: bool = False, service: InfrahubServices | None = None) -> None:
    global registry
    registry = InfrahubLockRegistry(local_only=local_only, service=service)


def build_object_lock_name(name: str) -> str:
    return f"global.object.{name}"
