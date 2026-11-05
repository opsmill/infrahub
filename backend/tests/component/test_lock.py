from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from prefect_redis.connection import aclose_redis_client
from pydantic import SecretStr
from redis.exceptions import LockNotOwnedError
from redis.exceptions import TimeoutError as RedisTimeoutError
from structlog.testing import capture_logs

from infrahub import config
from infrahub.config import CacheSettings
from infrahub.lock import LOCK_COMMAND_ATTEMPTS, LOCK_PREFIX, InfrahubLock
from infrahub.redis_connection import build_cache_connection_string, build_redis_connection
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    import redis.asyncio as redis
    from structlog.typing import EventDict

# A short read timeout lets a short delay stand in for one longer than redis-py's 5-second default.
READ_TIMEOUT_SECONDS = 0.2
LATE_REPLY_SECONDS = 0.5
PAUSE_MILLISECONDS = 500
NO_ANSWER_MILLISECONDS = 1500
TIMEOUT_WARNING = "Redis did not answer a lock command in time"
CLEAN_UP_WARNING = "Could not delete the key of a lock whose acquire timed out"


class ReplyDelayingProxy:
    """Forwards connections to Redis, and can hold back the next reply after Redis has run the command."""

    def __init__(self, host: str, port: int) -> None:
        self._upstream = (host, port)
        self._next_reply_delay = 0.0
        self._server: asyncio.Server | None = None
        self.port = 0

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server.close_clients()
            await self._server.wait_closed()

    def delay_next_reply(self, seconds: float) -> None:
        self._next_reply_delay = seconds

    async def _handle(self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
        upstream_reader, upstream_writer = await asyncio.open_connection(*self._upstream)
        await asyncio.gather(
            self._forward(client_reader, upstream_writer, delay=False),
            self._forward(upstream_reader, client_writer, delay=True),
            return_exceptions=True,
        )

    async def _forward(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, delay: bool) -> None:
        try:
            while data := await reader.read(65536):
                if delay and self._next_reply_delay:
                    seconds, self._next_reply_delay = self._next_reply_delay, 0.0
                    await asyncio.sleep(seconds)
                writer.write(data)
                await writer.drain()
        finally:
            writer.close()


@pytest.fixture
async def proxy(redis: dict[int, int] | None) -> AsyncGenerator[ReplyDelayingProxy, None]:
    cache = config.SETTINGS.cache
    proxy = ReplyDelayingProxy(host=cache.address, port=cache.service_port)
    await proxy.start()
    yield proxy
    await proxy.stop()


@pytest.fixture
async def redis_client(proxy: ReplyDelayingProxy) -> AsyncGenerator[redis.Redis, None]:
    cache = config.SETTINGS.cache
    through_proxy = CacheSettings(
        address="127.0.0.1",
        port=proxy.port,
        database=cache.database,
        username=cache.username,
        password=cache.password,
    )
    url = f"{build_cache_connection_string(through_proxy)}?socket_timeout={READ_TIMEOUT_SECONDS}"
    client = build_redis_connection(CacheSettings(url=SecretStr(url)))
    # Loads the release script on the server and opens a pooled connection, as earlier lock commands would have.
    warm_up = InfrahubLock(name=f"warm-up-{uuid4()}", connection=client, metrics=False)
    await warm_up.acquire()
    await warm_up.release()
    yield client
    await aclose_redis_client(client)


@pytest.fixture
async def direct_client(proxy: ReplyDelayingProxy) -> AsyncGenerator[redis.Redis, None]:
    client = build_redis_connection(config.SETTINGS.cache)
    yield client
    await aclose_redis_client(client)


def _events(records: list[EventDict], *names: str) -> list[tuple[str, str | None]]:
    return [(record["event"], record.get("command")) for record in records if record["event"] in names]


async def test_release_whose_reply_is_late_ends_released(redis_client: redis.Redis, proxy: ReplyDelayingProxy) -> None:
    """Redis ran the release before its reply timed out, so the repeat finds the key gone and nothing is left held."""
    lock = InfrahubLock(name=f"late-release-{uuid4()}", connection=redis_client, metrics=False)
    await lock.acquire()

    proxy.delay_next_reply(LATE_REPLY_SECONDS)
    with capture_logs() as records:
        await lock.release()

    assert await redis_client.get(f"{LOCK_PREFIX}.{lock.name}") is None
    assert _events(records, TIMEOUT_WARNING) == [(TIMEOUT_WARNING, "release")]


async def test_release_that_redis_dropped_is_repeated(redis_client: redis.Redis) -> None:
    """Redis discards a command whose client stopped waiting, so the release has to be sent again."""
    lock = InfrahubLock(name=f"dropped-release-{uuid4()}", connection=redis_client, metrics=False)
    await lock.acquire()

    await redis_client.client_pause(timeout=PAUSE_MILLISECONDS)
    await lock.release()

    assert await redis_client.get(f"{LOCK_PREFIX}.{lock.name}") is None


async def test_acquire_whose_reply_is_late_holds_the_lock(redis_client: redis.Redis, proxy: ReplyDelayingProxy) -> None:
    """Redis set the key before the reply timed out, so the repeated SET finds this acquisition's own token."""
    lock = InfrahubLock(name=f"late-acquire-{uuid4()}", connection=redis_client, metrics=False)
    key = f"{LOCK_PREFIX}.{lock.name}"

    proxy.delay_next_reply(LATE_REPLY_SECONDS)
    with capture_logs() as records:
        await lock.acquire()
    held = await redis_client.get(key)
    await lock.release()

    assert isinstance(held, bytes)
    assert held.decode().endswith(f"::{WORKER_IDENTITY}")
    assert await redis_client.get(key) is None
    assert _events(records, TIMEOUT_WARNING) == [(TIMEOUT_WARNING, "acquire")]


async def test_acquire_that_redis_dropped_is_repeated(redis_client: redis.Redis) -> None:
    lock = InfrahubLock(name=f"dropped-acquire-{uuid4()}", connection=redis_client, metrics=False)
    key = f"{LOCK_PREFIX}.{lock.name}"

    await redis_client.client_pause(timeout=PAUSE_MILLISECONDS)
    await lock.acquire()
    held = await redis_client.get(key)
    await lock.release()

    assert held is not None
    assert await redis_client.get(key) is None


async def test_acquire_gives_up_when_redis_stops_answering(redis_client: redis.Redis) -> None:
    """A request fails instead of waiting forever."""
    lock = InfrahubLock(name=f"no-answer-{uuid4()}", connection=redis_client, metrics=False)

    await redis_client.client_pause(timeout=NO_ANSWER_MILLISECONDS)
    with capture_logs() as records, pytest.raises(RedisTimeoutError, match=r"^Timeout reading from "):
        await lock.acquire()
    await asyncio.sleep(NO_ANSWER_MILLISECONDS / 1000)

    assert await redis_client.get(f"{LOCK_PREFIX}.{lock.name}") is None
    acquire_timeouts = [event for event in _events(records, TIMEOUT_WARNING) if event[1] == "acquire"]
    assert acquire_timeouts == [(TIMEOUT_WARNING, "acquire")] * LOCK_COMMAND_ATTEMPTS


async def test_acquire_that_gives_up_deletes_the_key_its_lost_set_created(
    redis_client: redis.Redis, proxy: ReplyDelayingProxy, direct_client: redis.Redis
) -> None:
    """Redis set the key, then stopped answering until after the acquire gave up, which must not leave the key held."""
    lock = InfrahubLock(name=f"lost-set-{uuid4()}", connection=redis_client, metrics=False)
    key = f"{LOCK_PREFIX}.{lock.name}"

    async def pause_once_the_key_is_set() -> None:
        # The SET runs inside the acquire, so its effect is watched on Redis rather than awaited here.
        for _ in range(200):
            if await direct_client.get(key) is not None:
                await direct_client.client_pause(timeout=NO_ANSWER_MILLISECONDS)
                return
            await asyncio.sleep(0.005)

    pause = asyncio.create_task(pause_once_the_key_is_set())
    proxy.delay_next_reply(LATE_REPLY_SECONDS)
    with capture_logs() as records, pytest.raises(RedisTimeoutError, match=r"^Timeout reading from "):
        await lock.acquire()
    await pause

    assert await direct_client.get(key) is None
    assert [record for record in records if record["event"] == CLEAN_UP_WARNING] == []


async def test_release_after_another_holder_took_the_key_keeps_that_holder_lock(redis_client: redis.Redis) -> None:
    """Two requests in one process share the lock object, so neither may release with, or clear, the other's token."""
    lock = InfrahubLock(name=f"moved-{uuid4()}", connection=redis_client, metrics=False)
    key = f"{LOCK_PREFIX}.{lock.name}"
    first_acquired = asyncio.Event()
    next_acquired = asyncio.Event()
    first_released = asyncio.Event()
    held_by_next: list[bytes | str | None] = []
    after_first_release: list[bytes | str | None] = []

    async def first_holder() -> None:
        await lock.acquire()
        first_acquired.set()
        await next_acquired.wait()
        try:
            # A lock without a TTL that was lost while held is reported to its holder.
            with pytest.raises(LockNotOwnedError, match=r"^Cannot release a lock that's no longer owned$"):
                await lock.release()
        finally:
            first_released.set()

    async def next_holder() -> None:
        await first_acquired.wait()
        # Stands in for the deadlock clean-up removing the key of a holder it took for dead.
        await redis_client.delete(key)
        await lock.acquire()
        held_by_next.append(await redis_client.get(key))
        next_acquired.set()
        await first_released.wait()
        after_first_release.append(await redis_client.get(key))
        await lock.release()

    await asyncio.gather(asyncio.create_task(first_holder()), asyncio.create_task(next_holder()))

    assert held_by_next[0] is not None
    assert after_first_release == held_by_next
    assert await redis_client.get(key) is None
