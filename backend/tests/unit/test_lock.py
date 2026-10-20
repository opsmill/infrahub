import operator
import time
from asyncio import gather, sleep
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from infrahub import config, lock
from infrahub.config import CacheSettings
from infrahub.core.timestamp import current_timestamp
from infrahub.lock import (
    GLOBAL_TASKMGR_INIT_LOCK,
    GLOBAL_WORKER_TASKMGR_INIT_LOCK,
    InfrahubLockRegistry,
    get_lock_cache_key,
    get_requested_at_from_lock_token,
    get_worker_id_from_lock_token,
)


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


@dataclass
class LockRequestedAtCase:
    name: str
    token: str | None
    expected: datetime | None


LOCK_REQUESTED_AT_CASES = [
    LockRequestedAtCase(
        name="valid",
        token="2026-01-01T10:20:30.123456Z::worker-7",
        expected=datetime(2026, 1, 1, 10, 20, 30, 123456, tzinfo=UTC),
    ),
    LockRequestedAtCase(name="none", token=None, expected=None),
    LockRequestedAtCase(name="empty", token="", expected=None),
    LockRequestedAtCase(name="no-separator", token="2026-01-01T10:20:30.123456Z", expected=None),
    LockRequestedAtCase(name="not-a-timestamp", token="yesterday::worker-7", expected=None),
    LockRequestedAtCase(name="no-offset", token="2026-01-01T10:20:30.123456::worker-7", expected=None),
    LockRequestedAtCase(name="empty-worker-id", token="2026-01-01T10:20:30.123456Z::", expected=None),
]


@pytest.mark.parametrize("case", LOCK_REQUESTED_AT_CASES, ids=[c.name for c in LOCK_REQUESTED_AT_CASES])
def test_get_requested_at_from_lock_token(case: LockRequestedAtCase) -> None:
    assert get_requested_at_from_lock_token(case.token) == case.expected


def test_the_request_time_of_a_token_written_by_a_lock_is_read_back() -> None:
    before = datetime.now(tz=UTC)

    requested_at = get_requested_at_from_lock_token(f"{current_timestamp()}::worker-7")

    assert requested_at is not None
    assert before <= requested_at <= datetime.now(tz=UTC)


def test_lock_cache_key_names_the_key_a_held_lock_is_stored_under() -> None:
    assert get_lock_cache_key(name="my-repository", namespace="repository") == "lock.repository.my-repository"


def test_lock_cache_key_matches_the_key_of_a_registry_lock() -> None:
    """The key is read by a process that does not hold the lock, so it must name what the lock writes."""
    held = InfrahubLockRegistry().get(name="my-repository", namespace="repository")

    assert held.remote.name == get_lock_cache_key(name="my-repository", namespace="repository")


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
        assert init_lock.remote.timeout == expected_ttl


async def test_regular_locks_have_no_ttl() -> None:
    if config.SETTINGS.cache.driver != config.CacheDriver.Redis:
        pytest.skip("TTL is only enforced with the Redis cache driver")

    registry = InfrahubLockRegistry(local_only=False)
    regular_lock = registry.get(name="repo-a", namespace="repository")

    assert regular_lock.ttl is None
    assert regular_lock.remote.timeout is None


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
