from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from infrahub.workers.read_cache import ExpiringModelCache

TTL_SECONDS = 60.0


class Definition(BaseModel):
    name: str
    tags: list[str] = []


class FakeClock:
    """Mutable monotonic clock advanced by hand; no real sleeps."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class RecordingSource:
    """Source that serves its current definitions, raises its current errors and records every key it is asked for."""

    def __init__(self, definitions: dict[UUID, Definition]) -> None:
        self.definitions = definitions
        self.errors: dict[UUID, Exception] = {}
        self.calls: list[UUID] = []

    async def read(self, key: UUID) -> Definition:
        self.calls.append(key)
        if key in self.errors:
            raise self.errors[key]
        return self.definitions[key]


class GatedSource:
    """Source whose reads all block until released, so that concurrent callers overlap."""

    def __init__(self, definition: Definition) -> None:
        self.definition = definition
        self.calls: list[UUID] = []
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def read(self, key: UUID) -> Definition:
        self.calls.append(key)
        self.started.set()
        await self.release.wait()
        return self.definition


async def test_a_key_is_served_from_memory_until_it_expires() -> None:
    key = uuid4()
    clock = FakeClock()
    source = RecordingSource(definitions={key: Definition(name="first")})
    cache = ExpiringModelCache(read=source.read, ttl_seconds=TTL_SECONDS, clock=clock)
    await cache.read(key=key)
    source.definitions[key] = Definition(name="re-saved")

    clock.advance(TTL_SECONDS - 0.1)
    before_expiry = await cache.read(key=key)
    clock.advance(0.1)
    at_expiry = await cache.read(key=key)

    assert before_expiry.name == "first"
    assert at_expiry.name == "re-saved"
    assert source.calls == [key, key]


async def test_each_key_is_read_from_the_source_on_its_own() -> None:
    first_key, second_key = uuid4(), uuid4()
    source = RecordingSource(definitions={first_key: Definition(name="first"), second_key: Definition(name="second")})
    cache = ExpiringModelCache(read=source.read, ttl_seconds=TTL_SECONDS, clock=FakeClock())

    names = [(await cache.read(key=key)).name for key in (first_key, second_key, first_key, second_key)]

    assert names == ["first", "second", "first", "second"]
    assert source.calls == [first_key, second_key]


async def test_a_failed_read_reaches_the_caller_and_the_next_read_retries() -> None:
    key = uuid4()
    source = RecordingSource(definitions={key: Definition(name="first")})
    source.errors[key] = ConnectionError("source unreachable")
    cache = ExpiringModelCache(read=source.read, ttl_seconds=TTL_SECONDS, clock=FakeClock())

    with pytest.raises(ConnectionError):
        await cache.read(key=key)
    del source.errors[key]

    assert (await cache.read(key=key)).name == "first"
    assert source.calls == [key, key]


async def test_an_expired_key_reports_the_source_error_instead_of_the_stale_model() -> None:
    key = uuid4()
    clock = FakeClock()
    source = RecordingSource(definitions={key: Definition(name="first")})
    cache = ExpiringModelCache(read=source.read, ttl_seconds=TTL_SECONDS, clock=clock)
    await cache.read(key=key)

    source.errors[key] = LookupError("deleted")
    clock.advance(TTL_SECONDS)

    with pytest.raises(LookupError):
        await cache.read(key=key)


async def test_concurrent_reads_of_a_missing_key_share_one_source_read() -> None:
    key = uuid4()
    source = GatedSource(definition=Definition(name="first"))
    cache = ExpiringModelCache(read=source.read, ttl_seconds=TTL_SECONDS, clock=FakeClock())

    async with asyncio.timeout(5):
        readers = [asyncio.create_task(cache.read(key=key)) for _ in range(3)]
        await source.started.wait()
        source.release.set()
        definitions = await asyncio.gather(*readers)

    assert [definition.name for definition in definitions] == ["first", "first", "first"]
    assert source.calls == [key]


async def test_changing_a_returned_model_leaves_later_reads_untouched() -> None:
    key = uuid4()
    source = RecordingSource(definitions={key: Definition(name="first", tags=["core"])})
    cache = ExpiringModelCache(read=source.read, ttl_seconds=TTL_SECONDS, clock=FakeClock())

    returned = await cache.read(key=key)
    returned.name = "changed"
    returned.tags.append("changed")

    assert await cache.read(key=key) == Definition(name="first", tags=["core"])
