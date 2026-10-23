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
from redis.exceptions import LockNotOwnedError, RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError

from infrahub import config
from infrahub.core.timestamp import current_timestamp
from infrahub.log import get_logger
from infrahub.redis_connection import build_cache_connection_string, build_redis_connection
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

# Each attempt waits up to the client's read timeout, so a few ride out a stall without hanging on a Redis that stopped
# answering.
LOCK_COMMAND_ATTEMPTS = 3


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


class RedisLock:
    """Lock held in Redis by one acquisition, whose commands are safe to repeat because each compares its token."""

    def __init__(self, connection: redis.Redis, name: str, ttl: int | None = None) -> None:
        self.name = name
        self.token: str | None = None
        self.connection = connection
        # Maximum lifetime in seconds for the lock.
        self.ttl = ttl
        self._lock = GlobalLock(redis=connection, name=name, timeout=ttl)

    async def acquire(self, token: str) -> None:
        """Wait until the key holds ``token``.

        Raises:
            redis.exceptions.TimeoutError: When Redis does not answer ``LOCK_COMMAND_ATTEMPTS`` times in a row.

        """
        timeouts = 0
        while True:
            try:
                # A SET whose reply was lost may still have run, so a key that already holds this token is acquired.
                if await self._lock.do_acquire(token) or await self._holds(token):
                    self.token = token
                    return
                timeouts = 0
            except RedisTimeoutError:
                timeouts += 1
                log.warning("Redis did not answer a lock command in time", lock=self.name, command="acquire")
                if timeouts == LOCK_COMMAND_ATTEMPTS:
                    await self._release_if_held(token)
                    raise
            await sleep(self._lock.sleep)

    async def release(self) -> None:
        """Delete the key if it still holds this acquisition's token.

        Raises:
            RuntimeError: When the lock has not been acquired.
            LockNotOwnedError: When the first attempt finds that the key no longer holds the token.
            redis.exceptions.TimeoutError: When Redis does not answer ``LOCK_COMMAND_ATTEMPTS`` times in a row.

        """
        token = self.token
        if token is None:
            raise RuntimeError("Lock release attempted without ownership context.")
        for attempt in range(1, LOCK_COMMAND_ATTEMPTS + 1):
            try:
                # Deleting compares this acquisition's token, so a repeat cannot release another holder's lock.
                await self._lock.do_release(token.encode())
            except RedisTimeoutError:
                log.warning("Redis did not answer a lock command in time", lock=self.name, command="release")
                if attempt == LOCK_COMMAND_ATTEMPTS:
                    raise
                await sleep(self._lock.sleep)
            except LockNotOwnedError:
                # After a timed-out attempt, the missing key is most likely the one that attempt deleted.
                if attempt == 1:
                    raise
                self.token = None
                return
            else:
                self.token = None
                return

    async def locked(self) -> bool:
        return await self._lock.locked()

    async def _holds(self, token: str) -> bool:
        stored = await self.connection.get(self.name)
        return (stored.decode() if isinstance(stored, bytes) else stored) == token

    async def _release_if_held(self, token: str) -> None:
        # Best effort while Redis is not answering: a key that a lost SET created holds only this token.
        self.token = token
        try:
            await self.release()
        except LockNotOwnedError:
            self.token = None
        except RedisError as exc:
            self.token = None
            log.warning("Could not delete the key of a lock whose acquire timed out", lock=self.name, error=str(exc))


class InfrahubLock:
    """InfrahubLock object to provide a unified interface for both Local and Distributed locks.

    Having the same interface for both local and distributed tests will simplify our unit tests.
    """

    def __init__(
        self,
        name: str,
        connection: redis.Redis | None = None,
        local: bool | None = None,
        in_multi: bool = False,
        metrics: bool = True,
        ttl: int | None = None,
    ) -> None:
        self.use_local: bool | None = local
        self.local: LocalLock = None
        self.remote: RedisLock = None
        self.name: str = name
        self.connection: redis.Redis | None = connection
        self.in_multi: bool = in_multi
        self.lock_type: str = "multi" if self.in_multi else "individual"
        self.event = asyncio.Event()
        self._recursion_var: ContextVar[int | None] = ContextVar(f"infrahub_lock_recursion_{self.name}", default=None)
        # Concurrent holders in one process share this object, so each acquisition keeps its own remote lock, token and
        # acquire time.
        self._held_remote: ContextVar[RedisLock | None] = ContextVar(f"infrahub_lock_remote_{self.name}", default=None)
        self._acquire_time: ContextVar[int | None] = ContextVar(f"infrahub_lock_acquire_time_{self.name}", default=None)
        self.metrics = metrics
        self.ttl: int | None = ttl

        if not self.connection or (self.use_local is None and name.startswith("local.")):
            self.use_local = True

        if self.use_local:
            self.local = LocalLock()
        else:
            self.remote = self._build_remote()

    def _build_remote(self) -> RedisLock:
        return RedisLock(connection=self.connection, name=f"{LOCK_PREFIX}.{self.name}", ttl=self.ttl)

    async def _acquire_remote(self) -> None:
        remote = self._build_remote()
        await remote.acquire(token=f"{current_timestamp()}::{WORKER_IDENTITY}")
        self._held_remote.set(remote)

    @property
    def acquire_time(self) -> int:
        value = self._acquire_time.get()
        if value is not None:
            return value

        raise ValueError("The lock has not been initialized")

    @acquire_time.setter
    def acquire_time(self, value: int) -> None:
        self._acquire_time.set(value)

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
                    await self._acquire_remote()
                else:
                    await self.local.acquire()
        elif not self.use_local:
            await self._acquire_remote()
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
            remote = self._held_remote.get()
            if remote is None:
                raise RuntimeError("Lock release attempted without ownership context.")
            self._held_remote.set(None)
            try:
                await remote.release()
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
        self.service = service
        self.connection_url: str | None = None
        if not local_only:
            self.connection_url = build_cache_connection_string(config.SETTINGS.cache)
            self.connection = build_redis_connection(config.SETTINGS.cache)
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
    # Rebuilding from unchanged arguments and cache settings would open a second client and leave this one open.
    if (
        not local_only
        and registry is not None
        and registry.service is service
        and registry.connection_url is not None
        and registry.connection_url == build_cache_connection_string(config.SETTINGS.cache)
    ):
        return
    registry = InfrahubLockRegistry(local_only=local_only, service=service)
