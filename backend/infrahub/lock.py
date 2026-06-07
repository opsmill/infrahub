from __future__ import annotations

import asyncio
import threading
import time
import uuid
import weakref
from asyncio import Lock as LocalLock
from asyncio import sleep
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

import redis.asyncio as redis
from prometheus_client import Histogram
from redis import UsernamePasswordCredentialProvider
from redis.asyncio.lock import Lock as GlobalLock

from infrahub import config
from infrahub.core.timestamp import current_timestamp
from infrahub.worker import get_worker_identity

if TYPE_CHECKING:
    from types import TracebackType

    from infrahub.services import InfrahubServices


class _LockRegistryProxy:
    """Per-event-loop lock registry (FR-024/FR-025).

    InfrahubLockRegistry holds loop-bound primitives: local ``asyncio.Lock``s
    and/or a redis async client whose connection pool has a loop-bound
    ``asyncio.Lock``. Under the embedded free-threaded backend each worker thread
    runs its own event loop, so a single shared registry gets awaited across
    loops ("bound to a different event loop"). This module-level proxy routes
    ``lock.registry.<attr>`` to the InfrahubLockRegistry that ``initialize_lock``
    built for the current loop. It is created once and never reassigned, so
    captured references (``self.x = lock.registry``) keep working. Cross-worker
    coordination still happens via the GLOBAL (redis) locks, which share the same
    keyspace regardless of which loop's redis client is used.
    """

    def __init__(self) -> None:
        self._by_loop: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, InfrahubLockRegistry]" = (
            weakref.WeakKeyDictionary()
        )
        self._lock = threading.Lock()

    def set_for_current_loop(self, lock_registry: InfrahubLockRegistry) -> None:
        with self._lock:
            self._by_loop[asyncio.get_running_loop()] = lock_registry

    def _current(self) -> InfrahubLockRegistry:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError as exc:
            raise RuntimeError("lock.registry accessed outside a running event loop") from exc
        with self._lock:
            lock_registry = self._by_loop.get(loop)
        if lock_registry is None:
            raise RuntimeError("lock registry is not initialised for the current event loop; call initialize_lock()")
        return lock_registry

    def __getattr__(self, name: str) -> Any:
        return getattr(self._current(), name)


# The module-level `registry` is a per-loop proxy (set once, never reassigned).
registry: InfrahubLockRegistry = _LockRegistryProxy()  # type: ignore[assignment]


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
GLOBAL_SCHEMA_LOCK = "global.schema"
GLOBAL_GRAPH_LOCK = "global.graph"


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

    def __init__(self, service: InfrahubServices, name: str) -> None:
        self.name = name
        self.token = None
        self.service = service

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
        token = f"{current_timestamp()}::{get_worker_identity()}"
        while True:
            if await self.do_acquire(token):
                self.token = token
                return
            await sleep(0.1)  # default Redis GlobalLock value

    async def do_acquire(self, token: str) -> bool | None:
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
        metrics: bool = True,
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

        if not self.connection or (self.use_local is None and name.startswith("local.")):
            self.use_local = True

        if self.use_local:
            self.local = LocalLock()
        elif config.SETTINGS.cache.driver == config.CacheDriver.Redis:
            self.remote = GlobalLock(redis=self.connection, name=f"{LOCK_PREFIX}.{self.name}")
        else:
            self.remote = NATSLock(service=self.connection, name=f"{LOCK_PREFIX}.{self.name}")

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
                    await self.remote.acquire(token=f"{current_timestamp()}::{get_worker_identity()}")
                else:
                    await self.local.acquire()
        elif not self.use_local:
            await self.remote.acquire(token=f"{current_timestamp()}::{get_worker_identity()}")
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
            await self.remote.release()
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
                credential_provider: UsernamePasswordCredentialProvider | None = None
                if config.SETTINGS.cache.username and config.SETTINGS.cache.password:
                    credential_provider = UsernamePasswordCredentialProvider(
                        username=config.SETTINGS.cache.username, password=config.SETTINGS.cache.password
                    )
                self.connection = redis.Redis(
                    host=config.SETTINGS.cache.address,
                    port=config.SETTINGS.cache.service_port,
                    db=config.SETTINGS.cache.database,
                    credential_provider=credential_provider,
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
    ) -> InfrahubLock:
        lock_name = self.name_generator.generate_name(name=name, namespace=namespace, local=local)
        if lock_name not in self.locks:
            self.locks[lock_name] = InfrahubLock(
                name=lock_name, connection=self.connection, in_multi=in_multi, metrics=metrics
            )
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
    # Per event loop (FR-024): store this worker loop's registry in the proxy
    # instead of reassigning the module global, so each loop uses its own
    # loop-bound redis/asyncio locks. Cross-worker coordination still goes through
    # the GLOBAL redis locks (shared keyspace).
    registry.set_for_current_loop(InfrahubLockRegistry(local_only=local_only, service=service))
