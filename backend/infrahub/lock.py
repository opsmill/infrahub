from __future__ import annotations

import asyncio
import time
import uuid
import weakref
from asyncio import Lock as LocalLock
from asyncio import sleep
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import datetime
from typing import TYPE_CHECKING

from prometheus_client import Histogram
from redis.asyncio.lock import Lock as GlobalLock
from redis.exceptions import LockNotOwnedError, RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError

from infrahub import config
from infrahub.core.timestamp import current_timestamp
from infrahub.exceptions import LockError, LockWaitTimeoutError
from infrahub.locks.shared_holders.factory import build_shared_holder_store
from infrahub.log import get_logger
from infrahub.redis_connection import build_cache_connection_string, build_redis_connection
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable
    from types import TracebackType

    import redis.asyncio as redis

    from infrahub.locks.shared_holders.interface import SharedHolderStore
    from infrahub.services import InfrahubServices


log = get_logger()

registry: InfrahubLockRegistry = None


METRIC_PREFIX = "infrahub_lock"
LOCK_PREFIX = "lock"

LOCK_ACQUIRE_TIME_METRICS = Histogram(
    f"{METRIC_PREFIX}_acquire_seconds",
    "Time to acquire the lock on a given object",
    labelnames=["lock", "type"],
    buckets=[0.0005, 0.25, 0.5, 1, 5, 30, 60, 120, 300],
)

LOCK_RESERVE_TIME_METRICS = Histogram(
    f"{METRIC_PREFIX}_reserved_duration_seconds",
    "Time while a given lock is reserved by a given client",
    labelnames=["lock", "type"],
    buckets=[0.001, 0.5, 1, 5, 10, 30, 60, 120, 300],
)

LOCAL_SCHEMA_LOCK = "local.schema"
GLOBAL_INIT_LOCK = "global.init"
GLOBAL_TASKMGR_INIT_LOCK = "global.taskmgr.init"
GLOBAL_WORKER_TASKMGR_INIT_LOCK = "global.worker.taskmgr.init"
GLOBAL_SCHEMA_LOCK = "global.schema"
GLOBAL_GRAPH_LOCK = "global.graph"
GLOBAL_INIT_LOCKS = frozenset({GLOBAL_INIT_LOCK, GLOBAL_TASKMGR_INIT_LOCK, GLOBAL_WORKER_TASKMGR_INIT_LOCK})
# Waiting for a schema refresh reads the local schema lock's event without holding the lock, and the global locks are few
# and used by every process, so these locks are kept for the life of the process.
PROCESS_LOCKS = frozenset({LOCAL_SCHEMA_LOCK, GLOBAL_SCHEMA_LOCK, GLOBAL_GRAPH_LOCK, *GLOBAL_INIT_LOCKS})

_LOCK_TOKEN_SEPARATOR = "::"

# Each attempt waits up to the client's read timeout, so a few ride out a stall without hanging on a Redis that stopped
# answering.
LOCK_COMMAND_ATTEMPTS = 3

# A shared holder renews its record this many times per time-to-live, so the record expires only after that many
# renewals in a row fail.
SHARED_LOCK_RENEWALS_PER_TTL = 3
EXCLUSIVE_LOCK_POLL_SECONDS = 0.1


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


def get_requested_at_from_lock_token(token: str | None) -> datetime | None:
    """Return when the worker in a ``"{timestamp}::{worker_id}"`` token asked for the lock, or ``None`` if malformed.

    The token is written before the worker waits for the lock, so this is not when the worker got it.
    """
    if not token:
        return None
    timestamp, separator, worker_id = token.partition(_LOCK_TOKEN_SEPARATOR)
    if not separator or not worker_id:
        return None
    try:
        requested_at = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    # A timestamp without an offset cannot be placed on the timeline, so it reads as unparseable.
    if requested_at.tzinfo is None:
        return None
    return requested_at


def get_lock_cache_key(name: str, namespace: str | None = None) -> str:
    """Return the cache key under which a held global lock stores its token."""
    return f"{LOCK_PREFIX}.{LockNameGenerator().generate_name(name=name, namespace=namespace)}"


def get_shared_holders_key(name: str) -> str:
    """Return the store key under which the holders of the shared lock `name` are recorded."""
    return f"{LOCK_PREFIX}.shared.{name}"


class InfrahubMultiLock:
    """Context manager to allow multiple locks to be reserved together."""

    def __init__(
        self, lock_registry: InfrahubLockRegistry, locks: list[str] | None = None, metrics: bool = True
    ) -> None:
        self.registry = lock_registry
        self.locks = locks or []
        self.metrics = metrics
        self._held: list[list[InfrahubLock]] = []
        """Locks taken by each acquisition not yet released, kept because the registry forgets a lock nothing references."""

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
        acquired: list[InfrahubLock] = []
        try:
            for lock_name in self.locks:
                lock = self.registry.get(name=lock_name, metrics=self.metrics)
                await lock.acquire()
                acquired.append(lock)
        except BaseException:
            # The context exit never runs when entering fails, so a partial acquisition is undone here.
            for lock in reversed(acquired):
                try:
                    await lock.release()
                except (RedisError, RuntimeError):
                    # The remaining locks still have to be released, and the caller has to receive the error that
                    # stopped the acquisition rather than this one.
                    log.exception("Could not release a lock after a multi-lock failed to acquire", lock=lock.name)
            raise
        self._held.append(acquired)

    async def release(self) -> None:
        if not self._held:
            return
        acquired = self._held[-1]
        while acquired:
            await acquired[-1].release()
            acquired.pop()
        self._held.pop()


class RedisLock:
    """Lock held in Redis by one acquisition, whose commands are safe to repeat because each compares its token."""

    def __init__(self, lock: GlobalLock) -> None:
        self.name = lock.name
        self.token: str | None = None
        self.connection = lock.redis
        # Maximum lifetime in seconds for the lock.
        self.ttl = lock.timeout
        self._lock = lock

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
        return RedisLock(lock=GlobalLock(redis=self.connection, name=f"{LOCK_PREFIX}.{self.name}", timeout=self.ttl))

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

        try:
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
        finally:
            # A task whose release failed must not re-enter the lock as if it still held it.
            self._recursion_var.set(None)
            self.event.set()

    async def locked(self) -> bool:
        if not self.use_local:
            return await self.remote.locked()

        return self.local.locked()

    def held_by_current_task(self) -> bool:
        return self._recursion_var.get() is not None


@dataclass(frozen=True)
class _SharedHold:
    depth: int
    holder: str
    renewal: asyncio.Task[None]


class InfrahubSharedLock:
    """A lock that many holders take in shared mode at once, and a single holder takes in exclusive mode.

    The exclusive mode is the plain lock of the same name, which a shared request also takes while it records
    itself, so a shared request queues behind an exclusive one that waits for the shared holders to finish.
    Taking that plain lock directly does not wait for the shared holders, so a name used here must not also be
    taken as a plain lock.
    """

    def __init__(
        self,
        name: str,
        mutex: InfrahubLock,
        store: SharedHolderStore,
        ttl_seconds: int,
        wait_seconds: float,
        poll_seconds: float = EXCLUSIVE_LOCK_POLL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = name
        self._mutex = mutex
        self._store = store
        self._ttl_seconds = ttl_seconds
        self._wait_seconds = wait_seconds
        self._poll_seconds = poll_seconds
        self._clock = clock
        self._holders_key = get_shared_holders_key(name=name)
        self._hold: ContextVar[_SharedHold | None] = ContextVar(f"infrahub_shared_lock_{name}", default=None)

    @asynccontextmanager
    async def shared(self) -> AsyncGenerator[None]:
        await self.acquire_shared()
        try:
            yield
        finally:
            await self.release_shared()

    @asynccontextmanager
    async def exclusive(self) -> AsyncGenerator[None]:
        await self.acquire_exclusive()
        try:
            yield
        finally:
            await self.release_exclusive()

    async def acquire_shared(self) -> None:
        hold = self._hold.get()
        if hold is not None:
            self._hold.set(replace(hold, depth=hold.depth + 1))
            return

        holder = str(uuid.uuid4())
        token = f"{current_timestamp()}{_LOCK_TOKEN_SEPARATOR}{WORKER_IDENTITY}"
        written = False
        try:
            with LOCK_ACQUIRE_TIME_METRICS.labels(self.name, "shared").time():
                # Recorded even under this task's exclusive hold, which can end before this shared one does.
                async with self._mutex:
                    written = True
                    await self._store.add(
                        key=self._holders_key, holder=holder, token=token, ttl_seconds=self._ttl_seconds
                    )
        except BaseException:
            # The write may have reached the store before the failure, and no release will follow to remove it.
            if written:
                await self._remove_record(holder=holder)
            raise
        renewal = asyncio.create_task(self._renew(holder=holder, token=token))
        self._hold.set(_SharedHold(depth=1, holder=holder, renewal=renewal))

    async def release_shared(self) -> None:
        hold = self._hold.get()
        if hold is None:
            raise RuntimeError("Lock release attempted without ownership context.")
        if hold.depth > 1:
            self._hold.set(replace(hold, depth=hold.depth - 1))
            return

        self._hold.set(None)
        hold.renewal.cancel()
        try:
            await asyncio.gather(hold.renewal, return_exceptions=True)
        finally:
            # A cancellation of this task, before or during the removal, would otherwise leave the record behind.
            await asyncio.shield(self._remove_record(holder=hold.holder))

    async def _remove_record(self, holder: str) -> None:
        """Remove the holder's record; raises nothing but cancellation."""
        try:
            await self._store.remove(key=self._holders_key, holder=holder)
        # Cleanup after the holder's work, whose outcome a failed removal must not replace; the record expires unrenewed.
        except Exception:
            log.exception("Failed to remove a shared lock record", lock=self.name)

    async def acquire_exclusive(self) -> None:
        """Take the lock alone, once every shared holder has released it.

        A task that already holds the lock exclusively gets it again at once.

        Raises:
            LockError: When the current task holds the lock in shared mode only.
            LockWaitTimeoutError: When shared holders remain after the wait limit; the lock is not held then.

        """
        if self._mutex.held_by_current_task():
            # Other tasks record a shared hold only under the mutex, so every holder left is this task's own.
            await self._mutex.acquire()
            return
        if self._hold.get() is not None:
            raise LockError(f"The lock {self.name} is held in shared mode by this task and cannot be made exclusive")

        await self._mutex.acquire()
        try:
            deadline = self._clock() + self._wait_seconds
            while await self._store.has_holders(key=self._holders_key):
                if self._clock() >= deadline:
                    raise LockWaitTimeoutError(name=self.name, wait_seconds=self._wait_seconds)
                await sleep(self._poll_seconds)
        except BaseException:
            await self._mutex.release()
            raise

    async def release_exclusive(self) -> None:
        await self._mutex.release()

    def held_exclusively_by_current_task(self) -> bool:
        return self._mutex.held_by_current_task()

    async def _renew(self, holder: str, token: str) -> None:
        while True:
            await sleep(self._ttl_seconds / SHARED_LOCK_RENEWALS_PER_TTL)
            try:
                await self._store.add(key=self._holders_key, holder=holder, token=token, ttl_seconds=self._ttl_seconds)
            # A loop that must keep renewing after one failed write, since the record lapses once renewals stop.
            except Exception:
                log.exception("Failed to renew a shared lock record", lock=self.name)


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
        self.max_connections: int | None = None
        if not local_only:
            self.connection_url = build_cache_connection_string(config.SETTINGS.cache)
            self.max_connections = config.SETTINGS.cache.max_connections
            self.connection = build_redis_connection(config.SETTINGS.cache)
        else:
            self.connection = None

        self.token = token or str(uuid.uuid4())
        self.locks: weakref.WeakValueDictionary[str, InfrahubLock] = weakref.WeakValueDictionary()
        """Locks that something in this process still references, since names built from node IDs would otherwise pile up."""
        self._process_locks: dict[str, InfrahubLock] = {}
        self.shared_locks: weakref.WeakValueDictionary[str, InfrahubSharedLock] = weakref.WeakValueDictionary()
        """Shared locks that something in this process still references; each keeps its mutex in `locks`."""
        self.name_generator = name_generator or LockNameGenerator()
        self.shared_holder_store = build_shared_holder_store(connection=self.connection)

    def get_existing(
        self,
        name: str,
        namespace: str | None,
        local: bool | None = None,
    ) -> InfrahubLock | None:
        """Return the lock of this name if something in this process still references it or keeps it for its whole life."""
        lock_name = self.name_generator.generate_name(name=name, namespace=namespace, local=local)
        return self._find(lock_name=lock_name)

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
        existing = self._find(lock_name=lock_name)
        if existing is not None:
            return existing
        if ttl is None and lock_name in GLOBAL_INIT_LOCKS:
            ttl = _init_lock_ttl_seconds()
        new_lock = self._create_lock(name=lock_name, in_multi=in_multi, metrics=metrics, ttl=ttl)
        if lock_name in PROCESS_LOCKS:
            self._process_locks[lock_name] = new_lock
        else:
            self.locks[lock_name] = new_lock
        return new_lock

    def _find(self, lock_name: str) -> InfrahubLock | None:
        process_lock = self._process_locks.get(lock_name)
        if process_lock is not None:
            return process_lock
        return self.locks.get(lock_name)

    def _create_lock(self, name: str, in_multi: bool, metrics: bool, ttl: int | None) -> InfrahubLock:
        return InfrahubLock(name=name, connection=self.connection, in_multi=in_multi, metrics=metrics, ttl=ttl)

    def get_shared(self, name: str, namespace: str | None = None) -> InfrahubSharedLock:
        lock_name = self.name_generator.generate_name(name=name, namespace=namespace)
        existing = self.shared_locks.get(lock_name)
        if existing is not None:
            return existing
        new_lock = self._create_shared_lock(name=lock_name)
        self.shared_locks[lock_name] = new_lock
        return new_lock

    def _create_shared_lock(self, name: str) -> InfrahubSharedLock:
        return InfrahubSharedLock(
            name=name,
            mutex=self.get(name=name),
            store=self.shared_holder_store,
            ttl_seconds=config.SETTINGS.cache.shared_lock_ttl_secs,
            wait_seconds=config.SETTINGS.cache.exclusive_lock_wait_secs,
        )

    def local_schema_lock(self) -> InfrahubLock:
        return self.get(name=LOCAL_SCHEMA_LOCK)

    def initialization(self) -> InfrahubLock:
        return self.get(name=GLOBAL_INIT_LOCK)

    async def local_schema_wait(self) -> None:
        await self.get(name=LOCAL_SCHEMA_LOCK).event.wait()

    def global_schema_lock(self) -> InfrahubMultiLock:
        """Return the lock for a schema update.

        The global lock is taken before this process's schema lock, so an update queued behind another worker does
        not hold up branch creation or registry refreshes in this process, and a holder of a global lock can take the
        local lock without deadlock. Once it holds the global lock, the update waits for a registry refresh already
        running in this process.
        """
        return InfrahubMultiLock(lock_registry=self, locks=[GLOBAL_SCHEMA_LOCK, LOCAL_SCHEMA_LOCK])

    def global_graph_lock(self) -> InfrahubMultiLock:
        """Return the lock for a whole-graph change such as a merge or a rebase.

        This process's schema lock is not part of it, so branch creation and registry refreshes in this process go
        ahead during the graph change. A holder that changes this process's schema registry takes the local lock after
        the global ones, and waits there for a registry refresh already running in this process.
        """
        return InfrahubMultiLock(lock_registry=self, locks=[GLOBAL_GRAPH_LOCK, GLOBAL_SCHEMA_LOCK])


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
        and registry.max_connections == config.SETTINGS.cache.max_connections
    ):
        return
    registry = InfrahubLockRegistry(local_only=local_only, service=service)
