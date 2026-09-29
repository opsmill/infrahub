import asyncio
from typing import Any
from uuid import uuid4

import nats as nats_client
import pytest

from infrahub import config
from infrahub.services.adapters.cache.nats import NATSCache


async def test_set_and_get(nats: dict[int, int] | None) -> None:
    if config.SETTINGS.cache.driver != config.CacheDriver.NATS:
        pytest.skip("Must use NATS to run this test")

    cache = await NATSCache.new()
    key = f"ci_testing:{uuid4()}"
    value = "I exist"
    initial = await cache.get(key)
    await cache.set(key=key, value=value)
    after_set = await cache.get(key)

    assert initial is None
    assert after_set == value
    await cache.close_connection()


async def test_per_key_ttl_expires(nats: dict[int, int] | None) -> None:
    """A key written with an expiry is dropped by NATS once its per-key TTL elapses."""
    if config.SETTINGS.cache.driver != config.CacheDriver.NATS:
        pytest.skip("Must use NATS to run this test")

    cache = await NATSCache.new()
    key = f"ci_testing:{uuid4()}"
    await cache.set(key=key, value="temporary", expires=2)
    after_set = await cache.get(key)
    await asyncio.sleep(3)
    after_expiry = await cache.get(key)

    assert after_set == "temporary"
    assert after_expiry is None
    await cache.close_connection()


async def test_per_key_ttl_on_create(nats: dict[int, int] | None) -> None:
    """not_exists writes (create) also honor a per-key TTL and reject a second create."""
    if config.SETTINGS.cache.driver != config.CacheDriver.NATS:
        pytest.skip("Must use NATS to run this test")

    cache = await NATSCache.new()
    key = f"ci_testing:{uuid4()}"
    first = await cache.set(key=key, value="held", expires=2, not_exists=True)
    second = await cache.set(key=key, value="other", expires=2, not_exists=True)
    await asyncio.sleep(3)
    after_expiry = await cache.get(key)

    assert first is True
    assert second is False  # key already exists
    assert after_expiry is None  # the per-key TTL released it
    await cache.close_connection()


async def test_set_without_ttl_persists(nats: dict[int, int] | None) -> None:
    if config.SETTINGS.cache.driver != config.CacheDriver.NATS:
        pytest.skip("Must use NATS to run this test")

    cache = await NATSCache.new()
    key = f"ci_testing:{uuid4()}"
    await cache.set(key=key, value="permanent")
    await asyncio.sleep(2)
    after_wait = await cache.get(key)

    assert after_wait == "permanent"
    await cache.close_connection()


async def test_list_keys(nats: dict[int, int] | None) -> None:
    if config.SETTINGS.cache.driver != config.CacheDriver.NATS:
        pytest.skip("Must use NATS to run this test")

    cache = await NATSCache.new()
    base_key = f"ci_testing:{uuid4()}"
    iterations = 5
    for i in range(iterations):
        await cache.set(key=f"{base_key}:{i + 1}", value="value set")

    keys = await cache.list_keys(filter_pattern=f"{base_key}:*")

    assert len(keys) == iterations
    assert f"{base_key}:1" in keys
    assert f"{base_key}:5" in keys
    await cache.close_connection()


async def test_new_closes_the_connection_when_initialisation_does_not_finish(
    nats: dict[int, int] | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A connection the caller never receives is closed rather than left open."""
    if config.SETTINGS.cache.driver != config.CacheDriver.NATS:
        pytest.skip("Must use NATS to run this test")

    opened: list[nats_client.NATS] = []
    connected = asyncio.Event()
    connect = nats_client.connect

    async def recording_connect(*args: Any, **kwargs: Any) -> nats_client.NATS:
        connection = await connect(*args, **kwargs)
        opened.append(connection)
        connected.set()
        return connection

    async def never_finishes(**kwargs: Any) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(nats_client, "connect", recording_connect)
    monkeypatch.setattr(NATSCache, "_ensure_kv", staticmethod(never_finishes))

    initialising = asyncio.create_task(NATSCache.new())
    await asyncio.wait_for(connected.wait(), timeout=30)
    initialising.cancel()

    with pytest.raises(asyncio.CancelledError):
        await initialising

    assert len(opened) == 1
    assert opened[0].is_closed
