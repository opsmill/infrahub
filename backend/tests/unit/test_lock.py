import operator
import subprocess  # noqa: S404
import sys
import time
from asyncio import gather, sleep
from dataclasses import dataclass

import pytest
import redis.asyncio as redis
from redis.asyncio.lock import Lock as GlobalLock

from infrahub import config, lock
from infrahub.config import CacheSettings
from infrahub.exceptions import InitializationError
from infrahub.lock import (
    GLOBAL_TASKMGR_INIT_LOCK,
    GLOBAL_WORKER_TASKMGR_INIT_LOCK,
    LOCK_PREFIX,
    InfrahubLockRegistry,
    NATSLock,
    get_worker_id_from_lock_token,
)
from infrahub.services import InfrahubServices
from tests.adapters.cache import MemoryCache


@dataclass
class LockTokenCase:
    name: str
    token: str | None
    expected: str | None


LOCK_TOKEN_CASES = [
    LockTokenCase(name="valid", token="2026-01-01T00:00:00.000000Z::worker-7", expected="worker-7"),
    LockTokenCase(name="none", token=None, expected=None),
    LockTokenCase(name="empty", token="", expected=None),
    LockTokenCase(name="no-separator", token="no-separator", expected=None),
    LockTokenCase(name="empty-worker-id", token="2026-01-01T00:00:00.000000Z::", expected=None),
]


@pytest.mark.parametrize("case", LOCK_TOKEN_CASES, ids=[c.name for c in LOCK_TOKEN_CASES])
def test_get_worker_id_from_lock_token(case: LockTokenCase) -> None:
    assert get_worker_id_from_lock_token(case.token) == case.expected


async def do_nothing(id: str, wait_sec: float, lock_name: str = "test1") -> tuple[str, int, int]:
    """Function for testing a simple lock."""
    async with lock.registry.get(name=lock_name):
        start_time = time.time_ns()
        await sleep(delay=wait_sec)
        end_time = time.time_ns()

    return id, start_time, end_time


async def do_nothing_global_graph(id: str, wait_sec: float) -> tuple[str, int, int]:
    """Function for testing the global_graph_lock.

    After acquiring the locks, wait for the indicated amount and return the start time and the end time of the lock.
    """
    async with lock.registry.global_graph_lock():
        start_time = time.time_ns()
        await sleep(delay=wait_sec)
        end_time = time.time_ns()

    return id, start_time, end_time


async def test_simple_infrahub_lock() -> None:
    lock.initialize_lock(local_only=True)

    results = list(
        await gather(
            do_nothing(id="one", wait_sec=0.5),
            do_nothing(id="two", wait_sec=1),
        )
    )

    results.sort(key=operator.itemgetter(1))
    assert results[0][2] <= results[1][1]


async def test_multi_global_graph_lock() -> None:
    lock.initialize_lock(local_only=True)

    results = await gather(
        do_nothing_global_graph(id="one", wait_sec=0.5),
        do_nothing_global_graph(id="two", wait_sec=1),
        do_nothing(id="tree", wait_sec=1, lock_name="local.schema"),
    )

    assert results[0][2] <= results[1][1]
    assert results[0][2] <= results[2][1]


def test_generate_name() -> None:
    generate_name = lock.LockNameGenerator().generate_name

    assert generate_name("simple") == "simple"
    assert generate_name("simple.name") == "simple.name"
    assert generate_name("simple.name.test") == "simple.name.test"
    assert generate_name("simple.name", local=True) == "local.simple.name"
    assert generate_name("simple.name", namespace="other") == "other.simple.name"
    assert generate_name("simple", namespace="other", local=True) == "local.other.simple"
    assert generate_name("simple", namespace="other", local=False) == "global.other.simple"


def test_unpack_name() -> None:
    unpack_name = lock.LockNameGenerator().unpack_name

    assert unpack_name("simple") == ("simple", None, None)
    assert unpack_name("repository.simple") == ("simple", "repository", None)
    assert unpack_name("repository.simple-test") == ("simple-test", "repository", None)
    assert unpack_name("repository.simple-test.long-name") == ("simple-test.long-name", "repository", None)
    assert unpack_name("local.repository.simple") == ("simple", "repository", True)
    assert unpack_name("global.repository.simple") == ("simple", "repository", False)


def test_init_lock_ttl_defaults_to_twenty_minutes() -> None:
    assert CacheSettings.model_fields["init_lock_ttl_mins"].default == 20


async def test_init_locks_carry_configured_ttl() -> None:
    if config.SETTINGS.cache.driver != config.CacheDriver.Redis:
        pytest.skip("TTL is only enforced with the Redis cache driver")

    registry = InfrahubLockRegistry(local_only=False)
    expected_ttl = config.SETTINGS.cache.init_lock_ttl_mins * 60

    init_locks = [
        registry.initialization(),
        registry.get(name=GLOBAL_TASKMGR_INIT_LOCK),
        registry.get(name=GLOBAL_WORKER_TASKMGR_INIT_LOCK),
    ]

    for init_lock in init_locks:
        assert init_lock.ttl == expected_ttl
        assert isinstance(init_lock.remote, GlobalLock)
        assert init_lock.remote.timeout == expected_ttl


async def test_regular_locks_have_no_ttl() -> None:
    if config.SETTINGS.cache.driver != config.CacheDriver.Redis:
        pytest.skip("TTL is only enforced with the Redis cache driver")

    registry = InfrahubLockRegistry(local_only=False)
    regular_lock = registry.get(name="repo-a", namespace="repository")

    assert regular_lock.ttl is None
    assert isinstance(regular_lock.remote, GlobalLock)
    assert regular_lock.remote.timeout is None


def test_reading_the_registry_before_initialization_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """An un-initialized registry must announce itself, not read as a usable value."""
    monkeypatch.delattr(lock, "registry", raising=False)

    assert not lock.is_initialized()
    with pytest.raises(InitializationError, match="has not been initialized"):
        _ = lock.registry


def test_remote_lock_rejects_a_connection_the_driver_cannot_use(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each driver rejects being handed only the other driver's connection, at construction time."""
    unsupported = [
        (config.CacheDriver.NATS, redis.Redis(), None, "requires a cache adapter"),
        (config.CacheDriver.Redis, None, MemoryCache(), "requires a Redis connection"),
    ]

    for driver, connection, cache, expected in unsupported:
        monkeypatch.setattr(config.SETTINGS.cache, "driver", driver)
        with pytest.raises(TypeError, match=expected):
            lock.InfrahubLock(name="global.wrong-connection", connection=connection, cache=cache, local=False)


async def test_nats_driver_locks_through_the_service_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """A registry built from a service hands its locks the service's cache adapter, and nothing more."""
    monkeypatch.setattr(config.SETTINGS.cache, "driver", config.CacheDriver.NATS)
    cache = MemoryCache()
    registry = InfrahubLockRegistry(local_only=False, service=await InfrahubServices.new(cache=cache))

    lock_obj = registry.get(name="repo-a", namespace="repository")
    key = f"{LOCK_PREFIX}.repository.repo-a"

    assert isinstance(lock_obj.remote, NATSLock)
    async with lock_obj:
        assert await cache.get(key=key) is not None
    assert await cache.get(key=key) is None


def test_lock_module_does_not_import_the_services_layer() -> None:
    """``infrahub.lock`` is a primitive the services layer is built on, so importing it must not load that layer."""
    probe = "import sys, infrahub.lock; raise SystemExit(int('infrahub.services' in sys.modules))"
    result = subprocess.run([sys.executable, "-c", probe], check=False, capture_output=True, text=True)  # noqa: S603

    assert result.returncode == 0, result.stderr or "infrahub.lock imported infrahub.services"


async def test_reentrant_lock_allows_nested_acquisitions() -> None:
    lock.initialize_lock(local_only=True)

    events: list[str] = []

    async def reentrant_task() -> None:
        async with lock.registry.get(name="resource_pool.test"):
            events.append("outer acquired")
            async with lock.registry.get(name="resource_pool.test"):
                events.append("inner acquired")
                await sleep(delay=0.1)
            events.append("inner released")
            await sleep(delay=0.1)
        events.append("outer released")

    async def waiting_task() -> None:
        await sleep(delay=0.05)
        async with lock.registry.get(name="resource_pool.test"):
            events.append("waiter acquired")

    await gather(reentrant_task(), waiting_task())

    assert events == [
        "outer acquired",
        "inner acquired",
        "inner released",
        "outer released",
        "waiter acquired",
    ]
