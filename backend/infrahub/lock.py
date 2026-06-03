from __future__ import annotations

import asyncio
import time
import uuid
from asyncio import Lock as LocalLock
from asyncio import sleep
from contextvars import ContextVar
from typing import TYPE_CHECKING

from prometheus_client import Histogram
from redis.asyncio.lock import Lock as GlobalLock
from redis.exceptions import LockNotOwnedError

from infrahub import config
from infrahub.core.timestamp import current_timestamp
from infrahub.log import get_logger
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from types import TracebackType

    import redis.asyncio as redis

    from infrahub.services import InfrahubServices


log = get_logger()

registry: InfrahubLockRegistry = None


METRIC_PREFIX = "infrahub_lock"
LOCK_PREFIX = "lock"

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
GLOBAL_TASKMGR_INIT_LOCK = "global.taskmgr.init"
GLOBAL_WORKER_TASKMGR_INIT_LOCK = "global.worker.taskmgr.init"
GLOBAL_SCHEMA_LOCK = "global.schema"
GLOBAL_GRAPH_LOCK = "global.graph"
GLOBAL_INIT_LOCKS = frozenset({GLOBAL_INIT_LOCK, GLOBAL_TASKMGR_INIT_LOCK, GLOBAL_WORKER_TASKMGR_INIT_LOCK})

_LOCK_TOKEN_SEPARATOR = "::"


def get_worker_id_from_lock_token(token: str | None) -> str | None:
    """Return the worker id from a lock token, or ``None`` if it is absent or malformed.

    A held lock stores a token of the form ``"{timestamp}::{worker_id}"`` (written on acquire). This
    is the inverse, kept beside the token format so the two stay in sync. ``None`` for a missing or
    unparseable token means callers never mistake a dropped/garbled lock for one held by a worker.
    """
    if not token:
        return None
    _, separator, worker_id = token.partition(_LOCK_TOKEN_SEPARATOR)
    if not separator or not worker_id:
        return None
    return worker_id


class InfrahubMultiLock:
    """Context manager to allow multiple locks to be reserved together."""

    def __init__(
        self, lock_registry: InfrahubLockRegistry, locks: list[str] | None = None, metrics: bool = True
    ) -> None:
        self.registry = lock_registry
        self.locks = locks or []
        self.metrics = metrics

    async def __aenter__(self) -> None:
        await self.acquire()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.release()

    async def acquire(self) -> None:
        for lock in self.locks:
            await self.registry.get(name=lock, metrics=self.metrics).acquire()

    async def release(self) -> None:
        for lock in reversed(self.locks):
            await self.registry.get(name=lock, metrics=self.metrics).release()


class NATSLock:
    """Context manager to lock using NATS."""

    def __init__(self, service: InfrahubServices, name: str, ttl: int | None = None) -> None:
        self.name = name
        self.token: str | None = None
        self.service = service
        # Maximum lifetime in seconds for the lock.
        self.ttl = ttl

    async def __aenter__(self) -> None:
        await self.acquire()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.release()

    async def acquire(self, token: str | None = None) -> None:
        token = token or f"{current_timestamp()}::{WORKER_IDENTITY}"
        while True:
            if await self.do_acquire(token):
                self.token = token
                return
            await sleep(0.1)  # default Redis GlobalLock value

    async def do_acquire(self, token: str) -> bool | None:
        return await self.service.cache.set(key=self.name, value=token, not_exists=True, expires=self.ttl)

    async def release(self) -> None:
        if self.ttl is not None and await self.service.cache.get(key=self.name) != self.token:
            # The TTL elapsed and the lock may have been re-acquired by another worker; nothing of ours
            # to release.
            self.token = None
            return
        await self.service.cache.delete(key=self.name)
        self.token = None

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
        metrics: bool = True,
        ttl: int | None = None,
    ) -> None:
        self.use_local: bool | None = local
        self.local: LocalLock = None
        self.remote: GlobalLock = None
        self.name: str = name
        self.connection: redis.Redis | None = connection
        self.in_multi: bool = in_multi
        self.lock_type: str = "multi" if self.in_multi else "individual"
        self._acquire_time: int | None = None
        self.event = asyncio.Event()
        self._recursion_var: ContextVar[int | None] = ContextVar(f"infrahub_lock_recursion_{self.name}", default=None)
        self.metrics = metrics
        self.ttl: int | None = ttl

        if not self.connection or (self.use_local is None and name.startswith("local.")):
            self.use_local = True

        if self.use_local:
            self.local = LocalLock()
        elif config.SETTINGS.cache.driver == config.CacheDriver.Redis:
            self.remote = GlobalLock(redis=self.connection, name=f"{LOCK_PREFIX}.{self.name}", timeout=ttl)
        else:
            self.remote = NATSLock(service=self.connection, name=f"{LOCK_PREFIX}.{self.name}", ttl=ttl)

    @property
    def acquire_time(self) -> int:
        if self._acquire_time is not None:
            return self._acquire_time

        raise ValueError("The lock has not been initialized")

    @acquire_time.setter
    def acquire_time(self, value: int) -> None:
        self._acquire_time = value

    async def __aenter__(self) -> None:
        await self.acquire()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.release()

    async def acquire(self) -> None:
        depth = self._recursion_var.get()
        if depth is not None:
            self._recursion_var.set(depth + 1)
            return

        if self.metrics:
            with LOCK_ACQUIRE_TIME_METRICS.labels(self.name, self.lock_type).time():
                if not self.use_local:
                    await self.remote.acquire(token=f"{current_timestamp()}::{WORKER_IDENTITY}")
                else:
                    await self.local.acquire()
        elif not self.use_local:
            await self.remote.acquire(token=f"{current_timestamp()}::{WORKER_IDENTITY}")
        else:
            await self.local.acquire()

        self.acquire_time = time.time_ns()
        self.event.clear()
        self._recursion_var.set(1)

    async def release(self) -> None:
        depth = self._recursion_var.get()
        if depth is None:
            raise RuntimeError("Lock release attempted without ownership context.")

        if depth > 1:
            self._recursion_var.set(depth - 1)
            return

        if self.acquire_time is not None:
            duration_ns = time.time_ns() - self.acquire_time
            if self.metrics:
                LOCK_RESERVE_TIME_METRICS.labels(self.name, self.lock_type).observe(duration_ns / 1000000000)
            self.acquire_time = None

        if not self.use_local:
            try:
                await self.remote.release()
            except LockNotOwnedError:
                # When a TTL is set the lock may have auto-expired (and possibly been re-acquired by
                # another worker) before we got here. There is nothing left for us to release.
                if self.ttl is None:
                    raise
                log.warning("Lock expired before it could be released", lock=self.name, ttl=self.ttl)
        else:
            self.local.release()

        self._recursion_var.set(None)
        self.event.set()

    async def locked(self) -> bool:
        if not self.use_local:
            return await self.remote.locked()

        return self.local.locked()


class LockNameGenerator:
    local = "local"
    _global = "global"

    def generate_name(self, name: str, namespace: str | None = None, local: bool | None = None) -> str:
        if namespace is None and local is None:
            return name

        new_name = ""
        if local is True:
            new_name = f"{self.local}."
        elif local is False:
            new_name = f"{self._global}."

        if namespace is not None:
            new_name += f"{namespace}."
        new_name += name

        return new_name

    def unpack_name(self, name: str) -> tuple[str, str | None, bool | None]:
        local = None
        namespace = None

        parts = name.split(".")
        if parts[0] == self.local:
            local = True
            parts = parts[1:]
        elif parts[0] == self._global:
            local = False
            parts = parts[1:]

        if len(parts) > 1:
            namespace = parts[0]
            original_name = ".".join(parts[1:])
        else:
            original_name = parts[0]

        return original_name, namespace, local


class InfrahubLockRegistry:
    def __init__(
        self,
        token: str | None = None,
        local_only: bool = False,
        service: InfrahubServices | None = None,
        name_generator: LockNameGenerator | None = None,
    ) -> None:
        if not local_only:
            if config.SETTINGS.cache.driver == config.CacheDriver.Redis:
                # Imported lazily to avoid a startup import cycle through the services package.
                from infrahub.services.adapters.cache.connection import build_redis_connection

                self.connection = build_redis_connection(config.SETTINGS.cache)
            else:
                self.connection = service
        else:
            self.connection = None

        self.token = token or str(uuid.uuid4())
        self.locks: dict[str, InfrahubLock] = {}
        self.name_generator = name_generator or LockNameGenerator()

    def get_existing(
        self,
        name: str,
        namespace: str | None,
        local: bool | None = None,
    ) -> InfrahubLock | None:
        lock_name = self.name_generator.generate_name(name=name, namespace=namespace, local=local)
        if lock_name not in self.locks:
            return None
        return self.locks[lock_name]

    def get(
        self,
        name: str,
        namespace: str | None = None,
        local: bool | None = None,
        in_multi: bool = False,
        metrics: bool = True,
        ttl: int | None = None,
    ) -> InfrahubLock:
        lock_name = self.name_generator.generate_name(name=name, namespace=namespace, local=local)
        if ttl is None and lock_name in GLOBAL_INIT_LOCKS:
            ttl = _init_lock_ttl_seconds()
        if lock_name not in self.locks:
            self.locks[lock_name] = self._create_lock(name=lock_name, in_multi=in_multi, metrics=metrics, ttl=ttl)
        return self.locks[lock_name]

    def _create_lock(self, name: str, in_multi: bool, metrics: bool, ttl: int | None) -> InfrahubLock:
        return InfrahubLock(name=name, connection=self.connection, in_multi=in_multi, metrics=metrics, ttl=ttl)

    def local_schema_lock(self) -> InfrahubLock:
        return self.get(name=LOCAL_SCHEMA_LOCK)

    def initialization(self) -> InfrahubLock:
        return self.get(name=GLOBAL_INIT_LOCK)

    async def local_schema_wait(self) -> None:
        await self.get(name=LOCAL_SCHEMA_LOCK).event.wait()

    def global_schema_lock(self) -> InfrahubMultiLock:
        return InfrahubMultiLock(lock_registry=self, locks=[LOCAL_SCHEMA_LOCK, GLOBAL_SCHEMA_LOCK])

    def global_graph_lock(self) -> InfrahubMultiLock:
        return InfrahubMultiLock(lock_registry=self, locks=[LOCAL_SCHEMA_LOCK, GLOBAL_GRAPH_LOCK, GLOBAL_SCHEMA_LOCK])


def _init_lock_ttl_seconds() -> int:
    return config.SETTINGS.cache.init_lock_ttl_mins * 60


def initialize_lock(local_only: bool = False, service: InfrahubServices | None = None) -> None:
    global registry
    registry = InfrahubLockRegistry(local_only=local_only, service=service)
