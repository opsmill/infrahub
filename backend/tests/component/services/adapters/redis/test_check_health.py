from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub import config
from infrahub.exceptions import DependencyUnhealthyError
from infrahub.health import (
    DependencyCheck,
    DependencyHealth,
    DependencyName,
    DependencyStatus,
    ErrorCategory,
    HealthChecker,
    classify_error,
)
from infrahub.services.adapters.cache.redis import RedisCache
from infrahub.worker import WORKER_IDENTITY
from tests.helpers.utils import closed_local_port

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@pytest.fixture
async def cache(redis: dict[int, int] | None) -> AsyncIterator[RedisCache]:
    cache = RedisCache()
    try:
        yield cache
    finally:
        await cache.close_connection()


@pytest.fixture
async def unreachable_cache(redis: dict[int, int] | None) -> AsyncIterator[RedisCache]:
    """A cache client configured with an address where nothing listens."""
    previous = (config.SETTINGS.cache.address, config.SETTINGS.cache.port)
    config.SETTINGS.cache.address = "127.0.0.1"
    config.SETTINGS.cache.port = closed_local_port()
    try:
        cache = RedisCache()
        yield cache
        await cache.close_connection()
    finally:
        config.SETTINGS.cache.address, config.SETTINGS.cache.port = previous


@pytest.fixture
async def cache_refusing_writes(cache: RedisCache) -> AsyncIterator[RedisCache]:
    """The cache with a memory limit below its usage and no eviction, so Redis answers every write with an error."""
    previous = await cache.connection.config_get("maxmemory", "maxmemory-policy")
    previous_maxmemory, previous_policy = previous["maxmemory"], previous["maxmemory-policy"]
    if previous_maxmemory is None or previous_policy is None:
        pytest.fail("The cache did not report its memory settings")
    await cache.connection.config_set("maxmemory-policy", "noeviction")
    await cache.connection.config_set("maxmemory", "1")
    try:
        yield cache
    finally:
        await cache.connection.config_set("maxmemory", previous_maxmemory)
        await cache.connection.config_set("maxmemory-policy", previous_policy)


async def test_check_health_writes_a_key_that_expires(cache: RedisCache) -> None:
    key = f"health:check:{WORKER_IDENTITY}"
    await cache.delete(key=key)

    await cache.check_health()

    assert await cache.get(key=key) == "1"
    assert 0 < await cache.connection.ttl(key) <= 60


async def test_check_health_raises_when_the_cache_answers_but_refuses_writes(cache_refusing_writes: RedisCache) -> None:
    assert await cache_refusing_writes.connection.ping() is True

    with pytest.raises(DependencyUnhealthyError, match=r"^The cache refused a write$") as exc_info:
        await cache_refusing_writes.check_health()

    assert classify_error(exc_info.value) == ErrorCategory.UNAVAILABLE


async def test_unreachable_cache_is_reported_with_its_error_within_the_check_timeout(
    unreachable_cache: RedisCache,
) -> None:
    checker = HealthChecker(
        checks=[DependencyCheck(name=DependencyName.CACHE, check=unreachable_cache.check_health)],
        check_timeout=1,
        max_report_age=0,
    )

    report = await checker.report()

    assert report.dependencies == [
        DependencyHealth(
            name=DependencyName.CACHE, status=DependencyStatus.DOWN, error=ErrorCategory.CONNECTION_REFUSED
        )
    ]
