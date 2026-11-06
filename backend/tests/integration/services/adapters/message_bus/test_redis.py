from __future__ import annotations

import asyncio
import inspect
import time
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
import redis.asyncio as redis
import ujson

from infrahub import config
from infrahub.components import ComponentType
from infrahub.exceptions import WorkerTimeoutError
from infrahub.message_bus import messages
from infrahub.message_bus.messages.send_echo_request import SendEchoRequestResponse
from infrahub.message_bus.operations import execute_message
from infrahub.message_bus.types import MessageTTL
from infrahub.services import InfrahubServices
from infrahub.services.adapters.message_bus.redis import RedisMessageBus, StreamSubscription
from infrahub.worker import WORKER_IDENTITY
from infrahub.workers.dependencies import build_message_bus

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from fast_depends import Provider

    from infrahub.config import BrokerSettings
    from tests.adapters.log import FakeLogger


async def wait_until(
    condition: Callable[[], Any],
    timeout: float = 10.0,  # noqa: ASYNC109
    interval: float = 0.1,
) -> None:
    """Poll until the condition returns a truthy value.

    Waits for an outcome instead of guessing a duration, so tests stay stable
    on slow runners while finishing as soon as the state is reached.

    Raises:
        TimeoutError: If the condition still does not hold after the timeout.

    """
    deadline = time.monotonic() + timeout
    while True:
        result = condition()
        if inspect.isawaitable(result):
            result = await result
        if result:
            return
        if time.monotonic() > deadline:
            raise TimeoutError(f"Condition not met within {timeout}s")
        await asyncio.sleep(interval)


def _as_text(value: bytes | str) -> str:
    """Return a Redis reply value as text, decoding it when the client returned bytes."""
    return value.decode() if isinstance(value, bytes) else value


@dataclass
class StreamInfo:
    """Information about a Redis stream."""

    name: str
    length: int
    groups: list[str] = field(default_factory=list)


@dataclass
class ConsumerGroupInfo:
    """Information about a Redis consumer group."""

    name: str
    stream: str
    pending: int
    consumers: list[str] = field(default_factory=list)


@dataclass
class RedisManager:
    """Helper class for managing Redis resources during tests."""

    settings: BrokerSettings
    retry_timeout: int = 15
    _connection: redis.Redis | None = None

    @property
    def namespace(self) -> str:
        return self.settings.namespace

    async def get_connection(self) -> redis.Redis:
        """Get or create a Redis connection."""
        if self._connection is None:
            self._connection = redis.Redis(
                host=self.settings.address,
                port=self.settings.service_port,
                username=self.settings.username or None,
                password=self.settings.password or None,
                ssl=self.settings.tls_enabled,
                ssl_ca_certs=self.settings.tls_ca_file,
                ssl_cert_reqs="none" if self.settings.tls_insecure else "required",
                ssl_check_hostname=not self.settings.tls_insecure,
                decode_responses=True,
            )
        return self._connection

    async def cleanup(self) -> None:
        """Clean up all streams and keys with the test namespace."""
        conn = await self.get_connection()

        # Find and delete all keys with our namespace
        cursor = 0
        while True:
            cursor, keys = await conn.scan(cursor=cursor, match=f"{self.namespace}:*", count=100)
            if keys:
                await conn.delete(*keys)
            if cursor == 0:
                break

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._connection:
            await self._connection.aclose()
            self._connection = None

    async def get_streams(self, prefix: str = "") -> list[StreamInfo]:
        """Get information about streams matching the prefix."""
        conn = await self.get_connection()
        search_pattern = f"{self.namespace}:{prefix}*" if prefix else f"{self.namespace}:*"

        streams: list[StreamInfo] = []
        cursor = 0
        while True:
            cursor, keys = await conn.scan(cursor=cursor, match=search_pattern, count=100)
            for key in keys:
                key_type = await conn.type(key)
                if key_type == "stream":
                    length = await conn.xlen(key)
                    groups_info = await conn.xinfo_groups(key)
                    group_names = [g["name"] for g in groups_info]
                    streams.append(StreamInfo(name=_as_text(key), length=length, groups=group_names))
            if cursor == 0:
                break

        return streams

    async def get_consumer_groups(self, stream: str) -> list[ConsumerGroupInfo]:
        """Get consumer groups for a stream."""
        conn = await self.get_connection()
        try:
            groups_info = await conn.xinfo_groups(stream)
            result = []
            for group in groups_info:
                consumers_info = await conn.xinfo_consumers(stream, group["name"])
                consumer_names = [c["name"] for c in consumers_info]
                result.append(
                    ConsumerGroupInfo(
                        name=group["name"],
                        stream=stream,
                        pending=group["pending"],
                        consumers=consumer_names,
                    )
                )
            return result
        except redis.ResponseError:
            return []

    async def get_stream_messages(self, stream: str, count: int = 10) -> list[dict[str, Any]]:
        """Get messages from a stream."""
        conn = await self.get_connection()
        try:
            entries = await conn.xrange(stream, count=count)
            return [{"id": entry_id, "data": data} for entry_id, data in entries or []]
        except redis.ResponseError:
            return []

    async def publish_message(self, stream: str, routing_key: str, body: str, headers: dict | None = None) -> str:
        """Publish a message directly to a stream."""
        conn = await self.get_connection()
        entry_id = await conn.xadd(
            stream,
            {
                "routing_key": routing_key,
                "body": body,
                "headers": ujson.dumps(headers or {}),
            },
        )
        return _as_text(entry_id)


@pytest.fixture
async def redis_api(redis: dict[int, int] | None) -> AsyncGenerator[RedisManager, None]:
    """Fixture that provides a RedisManager for testing."""
    settings = deepcopy(config.SETTINGS.broker)
    settings.namespace = "integration-tests"
    settings.driver = config.BrokerDriver.Redis
    # Use cache settings for Redis connection since broker settings default to RabbitMQ port
    settings.address = config.SETTINGS.cache.address
    settings.port = config.SETTINGS.cache.port
    settings.username = config.SETTINGS.cache.username
    settings.password = config.SETTINGS.cache.password

    manager = RedisManager(settings=settings)
    await manager.cleanup()
    yield manager
    await manager.cleanup()
    await manager.close()


async def test_redis_initial_setup(redis_api: RedisManager) -> None:
    """Validates creation of streams and consumer groups."""
    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    try:
        _ = await InfrahubServices.new(message_bus=bus, component_type=ComponentType.API_SERVER)
        api_streams = await redis_api.get_streams()
    finally:
        await bus.shutdown()

    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.GIT_AGENT)
    try:
        _ = await InfrahubServices.new(message_bus=bus, component_type=ComponentType.GIT_AGENT)
        agent_rpcs_groups = await redis_api.get_consumer_groups(f"{redis_api.namespace}:rpcs")
    finally:
        await bus.shutdown()

    # The API server creates the work queue with its single consumer group so
    # work published before the first git worker boots is not lost
    rpcs_stream = next((s for s in api_streams if s.name == f"{redis_api.namespace}:rpcs"), None)
    assert rpcs_stream is not None
    assert rpcs_stream.groups == ["git-workers"]

    # Event subscriptions are group-less, so no events consumer group exists
    assert not any(f"{redis_api.namespace}-events" in s.groups for s in api_streams)

    # Check that the git worker uses the same work queue group
    assert any(g.name == "git-workers" for g in agent_rpcs_groups)


async def test_redis_publish(redis_api: RedisManager) -> None:
    """Validate that the adapter publishes messages to the correct stream."""
    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    normal_message = messages.SendEchoRequest(message="normal")
    try:
        _ = await InfrahubServices.new(message_bus=bus, component_type=ComponentType.API_SERVER)
        await bus.send(message=normal_message)
        await wait_until(lambda: redis_api.get_stream_messages(f"{redis_api.namespace}:rpcs"))
        rpcs_messages = await redis_api.get_stream_messages(f"{redis_api.namespace}:rpcs")
    finally:
        await bus.shutdown()

    assert len(rpcs_messages) >= 1
    message_data = rpcs_messages[0]["data"]
    parsed_message = ujson.loads(message_data["body"])
    parsed_message = messages.SendEchoRequest(**parsed_message)

    # Reset meta fields for comparison (similar to RabbitMQ test)
    normal_message.meta.priority = 3
    assert parsed_message == normal_message


async def test_redis_callback(redis_api: RedisManager, fake_log: FakeLogger) -> None:
    """Validates that incoming messages get parsed by the callback method."""
    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    service = await InfrahubServices.new(message_bus=bus, component_type=ComponentType.API_SERVER)

    echo_message = messages.SendEchoRequest(message="Hello there")
    with patch("infrahub.message_bus.operations.send.echo.get_logger", return_value=fake_log):
        try:
            # Publish before the consumer's first read to ensure no message published
            # right after stream creation is dropped.
            await redis_api.publish_message(
                stream=bus.callback_stream,
                routing_key="send.echo.request",
                body=echo_message.body.decode(),
            )
            await wait_until(lambda: len(fake_log.info_logs) == 1)
        finally:
            await service.shutdown()

    assert fake_log.info_logs == ["Received message: Hello there"]
    assert fake_log.error_logs == []


async def test_redis_callback_with_invalid_routing_key(redis_api: RedisManager, fake_log: FakeLogger) -> None:
    """Validate that messages with an invalid routing key are logged as errors."""
    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    service = await InfrahubServices.new(message_bus=bus, component_type=ComponentType.API_SERVER)

    with patch("infrahub.services.adapters.message_bus.redis.get_logger", return_value=fake_log):
        try:
            await redis_api.publish_message(
                stream=bus.callback_stream,
                routing_key="event.branch.invalid",
                body="Completely invalid",
            )
            await wait_until(lambda: "Invalid message received" in fake_log.error_logs)
        finally:
            await service.shutdown()

    assert "Invalid message received" in fake_log.error_logs


async def _process_rpc_entry(
    message_id: str, message_data: dict[str, Any], bus: RedisMessageBus, redis_api: RedisManager
) -> None:
    """Process a single RPC entry from the stream."""
    routing_key = message_data.get("routing_key", "")
    body = message_data.get("body", "")
    if isinstance(body, str):
        body = body.encode()
    await execute_message(routing_key=routing_key, message_body=body, message_bus=bus)
    conn = await redis_api.get_connection()
    await conn.xack(f"{redis_api.namespace}:rpcs", RedisMessageBus.RPCS_GROUP, message_id)


async def _consume_rpc_messages(redis_api: RedisManager, bus: RedisMessageBus) -> None:
    """Consume and process RPC messages from the stream.

    Raises:
        TypeError: If the stream read does not return a list of streams.

    """
    conn = await redis_api.get_connection()
    while True:
        try:
            entries = await conn.xreadgroup(
                groupname=RedisMessageBus.RPCS_GROUP,
                consumername="test-consumer",
                streams={f"{redis_api.namespace}:rpcs": ">"},
                count=1,
                block=100,
            )
            if not isinstance(entries, list):
                raise TypeError(f"Expected a list of streams from the stream read, got {type(entries).__name__}")
            for _stream_name, stream_entries in entries:
                for message_id, message_data in stream_entries:
                    await _process_rpc_entry(message_id, message_data, bus, redis_api)
        except asyncio.CancelledError:
            break
        except redis.RedisError:
            break


async def test_redis_rpc(redis_api: RedisManager, fake_log: FakeLogger, dependency_provider: Provider) -> None:
    """Validates that RPC messages work correctly."""
    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    service = await InfrahubServices.new(message_bus=bus, component_type=ComponentType.API_SERVER)

    with dependency_provider.scope(build_message_bus, lambda: bus):
        consumer_task = asyncio.create_task(_consume_rpc_messages(redis_api, bus))

        try:
            response = await asyncio.wait_for(
                bus.rpc(
                    message=messages.SendEchoRequest(message="You can reply to this message"),
                    response_class=SendEchoRequestResponse,
                ),
                timeout=5.0,
            )
            assert response.data.response == "Reply to: You can reply to this message"
        finally:
            assert consumer_task.cancel() is True
            await service.shutdown()


async def test_redis_on_message(redis_api: RedisManager, fake_log: FakeLogger) -> None:
    """Validates the on_message method."""
    # First create an API server bus to set up the streams
    api_bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    await api_bus.shutdown()

    # Now create a GIT_AGENT bus which will consume messages
    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.GIT_AGENT)

    with patch("infrahub.message_bus.operations.send.echo.get_logger", return_value=fake_log):
        try:
            await bus.send(message=messages.SendEchoRequest(message="Hello there"))
            await wait_until(lambda: len(fake_log.info_logs) == 1)
        finally:
            await bus.shutdown()

    assert fake_log.info_logs == ["Received message: Hello there"]
    assert fake_log.error_logs == []


async def test_redis_on_message_invalid_routing_key(redis_api: RedisManager, fake_log: FakeLogger) -> None:
    """Validates logging of invalid routing key."""
    # First create an API server bus to set up the streams
    api_bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    await api_bus.shutdown()

    # Now create a GIT_AGENT bus which will consume messages
    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.GIT_AGENT)

    with patch("infrahub.services.adapters.message_bus.redis.get_logger", return_value=fake_log):
        try:
            await bus.publish(
                routing_key="request.something.invalid", message=messages.SendEchoRequest(message="Hello there")
            )
            await wait_until(lambda: len(fake_log.error_logs) == 1)
        finally:
            await bus.shutdown()

    assert fake_log.info_logs == []
    assert fake_log.error_logs == ["Invalid message received"]


async def test_redis_event_broadcast(redis_api: RedisManager, fake_log: FakeLogger) -> None:
    """Validates that events are delivered to every worker, including the publisher."""
    api_bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    git_bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.GIT_AGENT)

    with patch("infrahub.services.adapters.message_bus.redis.get_logger", return_value=fake_log):
        try:
            await api_bus.publish(
                message=messages.SendEchoRequest(message="broadcast"), routing_key="refresh.registry.invalid"
            )
            await wait_until(lambda: len(fake_log.error_logs) == 2)
        finally:
            await api_bus.shutdown()
            await git_bus.shutdown()

    assert fake_log.error_logs == ["Invalid message received", "Invalid message received"]


async def test_redis_event_binding_filter(redis_api: RedisManager, fake_log: FakeLogger) -> None:
    """Validates that workers ignore events outside their bindings."""
    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)

    with patch("infrahub.services.adapters.message_bus.redis.get_logger", return_value=fake_log):
        try:
            # refresh.git.* events are only bound by git workers, the API server must skip them
            await bus.publish(message=messages.SendEchoRequest(message="git only"), routing_key="refresh.git.invalid")
            await bus.publish(
                message=messages.SendEchoRequest(message="for api"), routing_key="refresh.registry.invalid"
            )
            # Entries are consumed in order, so an error for the second event alone proves the first was skipped.
            await wait_until(lambda: len(fake_log.error_logs) == 1)
        finally:
            await bus.shutdown()

    assert fake_log.error_logs == ["Invalid message received"]


async def test_redis_delayed_retry_republished(redis_api: RedisManager) -> None:
    """Validates that failed-message retries are re-published after their delay."""
    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    conn = await redis_api.get_connection()
    rpcs_stream = f"{redis_api.namespace}:rpcs"
    delayed_queue = f"{redis_api.namespace}:delayed"

    try:
        await bus.send(message=messages.SendEchoRequest(message="try again"), delay=MessageTTL.FIVE, is_retry=True)

        # The pending retry is durably recorded before the publish call returns
        assert await conn.zcard(delayed_queue) == 1
        assert await conn.xlen(rpcs_stream) == 0

        await wait_until(lambda: conn.xlen(rpcs_stream))
    finally:
        await bus.shutdown()

    assert await conn.xlen(rpcs_stream) == 1
    assert await conn.zcard(delayed_queue) == 0


async def test_redis_delayed_retry_survives_publisher_shutdown(redis_api: RedisManager) -> None:
    """Validates that a pending retry outlives the worker that scheduled it."""
    publisher = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    conn = await redis_api.get_connection()
    rpcs_stream = f"{redis_api.namespace}:rpcs"

    try:
        await publisher.send(message=messages.SendEchoRequest(message="survivor"), delay=MessageTTL.FIVE, is_retry=True)
    finally:
        await publisher.shutdown()

    assert await conn.zcard(f"{redis_api.namespace}:delayed") == 1

    other_worker = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    try:
        await wait_until(lambda: conn.xlen(rpcs_stream))
    finally:
        await other_worker.shutdown()

    stream_messages = await redis_api.get_stream_messages(rpcs_stream)
    assert len(stream_messages) == 1
    delivered = messages.SendEchoRequest(**ujson.loads(stream_messages[0]["data"]["body"]))
    assert delivered.message == "survivor"
    assert stream_messages[0]["data"]["routing_key"] == "send.echo.request"


async def test_redis_delayed_delivery_dead_letters_bad_entries(redis_api: RedisManager, fake_log: FakeLogger) -> None:
    """Validates that an undeliverable delayed entry neither blocks nor duplicates the other entries.

    Failing entries are retried with a backoff and parked in the dead-letter
    list once their attempts are exhausted, instead of being retried forever.
    """
    conn = await redis_api.get_connection()
    delayed_queue = f"{redis_api.namespace}:delayed"
    poison_stream = f"{redis_api.namespace}:poison"
    good_stream = f"{redis_api.namespace}:rpcs"

    # XADD onto a key holding a plain string fails with WRONGTYPE
    await conn.set(poison_stream, "not-a-stream")

    entry_fields = {"routing_key": "send.echo.request", "body": "{}", "headers": "{}", "priority": "3"}
    poison_member = ujson.dumps({"id": "poison", "stream": poison_stream, "fields": entry_fields})
    good_member = ujson.dumps({"id": "good", "stream": good_stream, "fields": entry_fields})
    malformed_member = "not json"
    # All three entries are due immediately; the failing ones sort first
    await conn.zadd(delayed_queue, {poison_member: 1, malformed_member: 2, good_member: 3})

    bus = RedisMessageBus(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    bus.DELAYED_POLL_INTERVAL = 0.2
    bus.DELAYED_RETRY_DELAY_MS = 100
    bus.DELAYED_MAX_ATTEMPTS = 2

    async def all_bad_entries_parked() -> bool:
        return await conn.llen(f"{redis_api.namespace}:delayed:dead") == 2

    with patch("infrahub.services.adapters.message_bus.redis.get_logger", return_value=fake_log):
        try:
            await bus._initialize()
            await wait_until(all_bad_entries_parked)
        finally:
            await bus.shutdown()

    assert await conn.xlen(good_stream) == 1
    assert await conn.zcard(delayed_queue) == 0
    dead_members = await conn.lrange(f"{redis_api.namespace}:delayed:dead", 0, -1)
    assert set(dead_members) == {poison_member, malformed_member}
    assert await conn.hlen(f"{redis_api.namespace}:delayed:attempts") == 0
    assert "Failed to deliver delayed messages, retrying after a delay" in fake_log.warning_logs
    assert "Parked undeliverable delayed messages in the dead-letter list" in fake_log.error_logs


async def test_redis_pending_messages_reclaimed(redis_api: RedisManager, fake_log: FakeLogger) -> None:
    """Validates that unacknowledged messages of dead consumers are re-processed."""
    api_bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    try:
        await api_bus.send(message=messages.SendEchoRequest(message="orphaned"))
    finally:
        await api_bus.shutdown()

    # Simulate a worker that died mid-processing: deliver without acknowledging
    conn = await redis_api.get_connection()
    entries = await conn.xreadgroup(
        groupname=RedisMessageBus.RPCS_GROUP,
        consumername="dead-worker",
        streams={f"{redis_api.namespace}:rpcs": ">"},
        count=1,
    )
    assert entries

    git_bus = RedisMessageBus(settings=redis_api.settings, component_type=ComponentType.GIT_AGENT)
    git_bus.CLAIM_IDLE_MS = 0  # claim at once instead of after a minute of idleness
    with patch("infrahub.message_bus.operations.send.echo.get_logger", return_value=fake_log):
        try:
            await git_bus._initialize()
            await wait_until(lambda: len(fake_log.info_logs) == 1)
        finally:
            await git_bus.shutdown()

    assert fake_log.info_logs == ["Received message: orphaned"]
    assert fake_log.error_logs == []


async def test_redis_worked_stream_trimmed(redis_api: RedisManager, fake_log: FakeLogger) -> None:
    """Validates that acknowledged entries are trimmed from the work queue."""
    api_bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    git_bus = RedisMessageBus(settings=redis_api.settings, component_type=ComponentType.GIT_AGENT)
    git_bus.MAINTENANCE_INTERVAL = 0.5

    conn = await redis_api.get_connection()
    rpcs_stream = f"{redis_api.namespace}:rpcs"

    async def worked_entries_trimmed() -> bool:
        return await conn.xlen(rpcs_stream) <= 1

    with patch("infrahub.message_bus.operations.send.echo.get_logger", return_value=fake_log):
        try:
            await git_bus._initialize()
            for index in range(3):
                await api_bus.send(message=messages.SendEchoRequest(message=f"echo {index}"))
            await wait_until(lambda: len(fake_log.info_logs) == 3)
            # Everything before the last delivered entry is trimmed away
            await wait_until(worked_entries_trimmed)
        finally:
            await git_bus.shutdown()
            await api_bus.shutdown()

    assert len(fake_log.info_logs) == 3
    assert fake_log.error_logs == []
    assert await conn.xlen(rpcs_stream) <= 1


async def test_redis_consumer_deregistered_on_shutdown(redis_api: RedisManager) -> None:
    """Validates that a worker removes its work queue consumer when shutting down."""
    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.GIT_AGENT)

    async def consumer_registered() -> bool:
        groups = await redis_api.get_consumer_groups(f"{redis_api.namespace}:rpcs")
        rpcs_group = next((g for g in groups if g.name == RedisMessageBus.RPCS_GROUP), None)
        return bool(rpcs_group and rpcs_group.consumers)

    try:
        await wait_until(consumer_registered)
        groups = await redis_api.get_consumer_groups(f"{redis_api.namespace}:rpcs")
    finally:
        await bus.shutdown()

    rpcs_group = next(g for g in groups if g.name == RedisMessageBus.RPCS_GROUP)
    assert rpcs_group.consumers == [f"git-worker-{WORKER_IDENTITY}"]

    groups = await redis_api.get_consumer_groups(f"{redis_api.namespace}:rpcs")
    rpcs_group = next(g for g in groups if g.name == RedisMessageBus.RPCS_GROUP)
    assert rpcs_group.consumers == []


async def test_redis_orphaned_callback_stream_expires(redis_api: RedisManager) -> None:
    """Validates that a callback stream whose worker never cleans up carries an expiry."""
    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.GIT_AGENT)
    conn = await redis_api.get_connection()
    # Nothing reads or refreshes this stream, as when its worker died without cleaning up
    requester_callback_stream = f"{redis_api.namespace}:callback:other-worker"

    try:
        for index in range(3):
            await bus.reply(
                message=messages.SendEchoRequest(message=f"reply {index}"), routing_key=requester_callback_stream
            )
    finally:
        await bus.shutdown()

    assert await conn.xlen(requester_callback_stream) == 3
    assert 0 < await conn.ttl(requester_callback_stream) <= RedisMessageBus.CALLBACK_STREAM_TTL


async def test_redis_callback_stream_trimmed_after_read(redis_api: RedisManager, fake_log: FakeLogger) -> None:
    """Validates that a worker trims its own callback stream once replies are read."""
    bus = RedisMessageBus(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    bus.MAINTENANCE_INTERVAL = 0.5
    conn = await redis_api.get_connection()

    async def read_entries_trimmed() -> bool:
        return await conn.xlen(bus.callback_stream) <= 1

    with patch("infrahub.services.adapters.message_bus.redis.get_logger", return_value=fake_log):
        try:
            await bus._initialize()
            for index in range(20):
                reply = messages.SendEchoRequest(message=f"reply {index}")
                reply.meta.correlation_id = f"expired-{index}"
                await bus.reply(message=reply, routing_key=bus.callback_stream)
            await wait_until(lambda: len(fake_log.info_logs) == 20)
            await wait_until(read_entries_trimmed)
            length = await conn.xlen(bus.callback_stream)
            ttl = await conn.ttl(bus.callback_stream)
        finally:
            await bus.shutdown()

    # Every reply was read (and discarded as expired), then trimmed away; only
    # the newest read entry may remain below the trim threshold. The owner
    # also keeps the stream's expiry refreshed.
    assert len(fake_log.info_logs) == 20
    assert length <= 1
    assert 0 < ttl <= RedisMessageBus.CALLBACK_STREAM_TTL


async def test_redis_rpc_timeout(redis_api: RedisManager) -> None:
    """Validates that an RPC call fails cleanly when no worker replies."""
    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)

    try:
        with pytest.raises(WorkerTimeoutError) as exc:
            await bus.rpc(
                message=messages.SendEchoRequest(message="nobody is listening"),
                response_class=SendEchoRequestResponse,
                timeout=1,
            )

        assert exc.value.message == "No worker answered send.echo.request within 1 seconds"
        assert bus.futures == {}

        # An explicit zero must time out immediately instead of selecting the default
        with pytest.raises(WorkerTimeoutError) as exc:
            await bus.rpc(
                message=messages.SendEchoRequest(message="nobody is listening"),
                response_class=SendEchoRequestResponse,
                timeout=0,
            )

        assert exc.value.message == "No worker answered send.echo.request within 0 seconds"
        assert bus.futures == {}
    finally:
        await bus.shutdown()


@dataclass
class DelayedPublishCase:
    name: str
    routing_key: str
    scheduled_entries: int
    dropped: bool


@pytest.mark.parametrize(
    "case",
    [
        DelayedPublishCase(
            name="broadcast_event_is_dropped",
            routing_key="refresh.registry.branches",
            scheduled_entries=0,
            dropped=True,
        ),
        DelayedPublishCase(
            name="work_item_is_scheduled", routing_key="send.echo.request", scheduled_entries=1, dropped=False
        ),
    ],
    ids=lambda case: case.name,
)
async def test_redis_delayed_publish(case: DelayedPublishCase, redis_api: RedisManager, fake_log: FakeLogger) -> None:
    """A delayed broadcast event is dropped, since every worker would deliver it again, while a delayed work item waits."""
    with patch("infrahub.services.adapters.message_bus.redis.get_logger", return_value=fake_log):
        bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
        try:
            await bus.publish(
                message=messages.SendEchoRequest(message="retry"),
                routing_key=case.routing_key,
                delay=MessageTTL.FIVE,
                is_retry=True,
            )
        finally:
            await bus.shutdown()

    conn = await redis_api.get_connection()
    assert await conn.zcard(f"{redis_api.namespace}:delayed") == case.scheduled_entries
    assert ("Dropping the delayed delivery of a broadcast event" in fake_log.warning_logs) is case.dropped


async def test_redis_refused_maintenance_does_not_stop_the_work_queue(
    redis_api: RedisManager, fake_log: FakeLogger
) -> None:
    """A maintenance command the server keeps refusing still lets the worker consume its work queue."""
    api_bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    await api_bus.shutdown()
    refused = AsyncMock(side_effect=redis.ResponseError("NOPERM this user has no permissions to run 'xautoclaim'"))

    with (
        patch.object(RedisMessageBus, "_claim_pending_messages", refused),
        patch("infrahub.message_bus.operations.send.echo.get_logger", return_value=fake_log),
    ):
        bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.GIT_AGENT)
        try:
            await bus.send(message=messages.SendEchoRequest(message="Hello there"))
            await wait_until(lambda: len(fake_log.info_logs) == 1)
        finally:
            await bus.shutdown()

    assert refused.await_count >= 1
    assert fake_log.info_logs == ["Received message: Hello there"]


async def test_redis_refused_maintenance_does_not_stop_the_callback_stream(
    redis_api: RedisManager, fake_log: FakeLogger
) -> None:
    """A maintenance command the server keeps refusing still lets the API server read its callback stream."""
    refused = AsyncMock(side_effect=redis.ResponseError("NOPERM this user has no permissions to run 'xtrim'"))

    with (
        patch.object(RedisMessageBus, "_maintain_owned_stream", refused),
        patch("infrahub.services.adapters.message_bus.redis.get_logger", return_value=fake_log),
    ):
        bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
        try:
            await redis_api.publish_message(
                stream=bus.callback_stream, routing_key="event.branch.invalid", body="Completely invalid"
            )
            await wait_until(lambda: "Invalid message received" in fake_log.error_logs)
        finally:
            await bus.shutdown()

    assert refused.await_count >= 1


class BlockingHandler:
    """Stands in for the message handler, recording each start and holding it until released."""

    def __init__(self) -> None:
        self.started: list[str] = []
        self.release = asyncio.Event()

    async def __call__(self, routing_key: str, message_body: bytes, message_bus: RedisMessageBus) -> None:
        self.started.append(routing_key)
        await self.release.wait()


async def test_redis_worker_runs_work_items_concurrently_up_to_the_limit(redis_api: RedisManager) -> None:
    """A worker runs as many work items at once as maximum_concurrent_messages allows, and the rest wait."""
    settings = redis_api.settings.model_copy(update={"maximum_concurrent_messages": 2})
    handler = BlockingHandler()

    with patch("infrahub.services.adapters.message_bus.redis.execute_message", handler):
        api_bus = await RedisMessageBus.new(settings=settings, component_type=ComponentType.API_SERVER)
        git_bus = await RedisMessageBus.new(settings=settings, component_type=ComponentType.GIT_AGENT)
        try:
            for index in range(3):
                await api_bus.send(message=messages.SendEchoRequest(message=f"work {index}"))
            await wait_until(lambda: len(handler.started) == 2)
            # Several stream reads pass while both handler slots are taken.
            await asyncio.sleep(RedisMessageBus.READ_BLOCK_MS * 3 / 1000)
            started_while_busy = len(handler.started)
            handler.release.set()
            await wait_until(lambda: len(handler.started) == 3)
        finally:
            handler.release.set()
            await git_bus.shutdown()
            await api_bus.shutdown()

    assert started_while_busy == 2


async def test_redis_events_run_concurrently(redis_api: RedisManager) -> None:
    """A slow event handler does not hold up the events published after it."""
    handler = BlockingHandler()

    with patch("infrahub.services.adapters.message_bus.redis.execute_message", handler):
        bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.GIT_AGENT)
        try:
            for routing_key in ("refresh.registry.branches", "refresh.registry.rebased_branch"):
                await bus.publish(message=messages.SendEchoRequest(message="event"), routing_key=routing_key)
            await wait_until(lambda: len(handler.started) == 2)
        finally:
            handler.release.set()
            await bus.shutdown()

    assert handler.started == ["refresh.registry.branches", "refresh.registry.rebased_branch"]


async def test_redis_stale_consumers_are_removed(redis_api: RedisManager) -> None:
    """Maintenance deletes a consumer that holds nothing and has stopped reading, and keeps one holding an entry."""
    api_bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    try:
        await api_bus.send(message=messages.SendEchoRequest(message="held"))
    finally:
        await api_bus.shutdown()

    conn = await redis_api.get_connection()
    rpcs_stream = f"{redis_api.namespace}:rpcs"

    async def consumer_names() -> set[str]:
        return {_as_text(info["name"]) for info in await conn.xinfo_consumers(rpcs_stream, RedisMessageBus.RPCS_GROUP)}

    await conn.xreadgroup(
        groupname=RedisMessageBus.RPCS_GROUP, consumername="busy-worker", streams={rpcs_stream: ">"}, count=1
    )
    await conn.xgroup_createconsumer(rpcs_stream, RedisMessageBus.RPCS_GROUP, "stale-worker")
    assert await consumer_names() == {"busy-worker", "stale-worker"}

    async def stale_consumer_removed() -> bool:
        return "stale-worker" not in await consumer_names()

    git_bus = RedisMessageBus(settings=redis_api.settings, component_type=ComponentType.GIT_AGENT)
    git_bus.STALE_CONSUMER_IDLE_MS = 0
    try:
        await git_bus._initialize()
        await wait_until(stale_consumer_removed)
        remaining = await consumer_names()
    finally:
        await git_bus.shutdown()

    assert "busy-worker" in remaining


@dataclass
class ListenCase:
    name: str
    topic: str
    expected: list[str]


@pytest.mark.parametrize(
    "case",
    [
        ListenCase(
            name="every_message",
            topic="#",
            expected=["refresh.git.fetch", "refresh.registry.branches", "send.echo.request"],
        ),
        ListenCase(
            name="matching_topic", topic="refresh.#", expected=["refresh.git.fetch", "refresh.registry.branches"]
        ),
    ],
    ids=lambda case: case.name,
)
async def test_redis_listen(case: ListenCase, redis_api: RedisManager) -> None:
    """A listener receives the events and work items matching its topic, and leaves work items to the workers."""
    conn = await redis_api.get_connection()
    events_stream = f"{redis_api.namespace}:events"
    rpcs_stream = f"{redis_api.namespace}:rpcs"
    await conn.xgroup_create(rpcs_stream, RedisMessageBus.RPCS_GROUP, id="0", mkstream=True)
    received: list[tuple[str, bytes]] = []

    async def listener(routing_key: str, body: bytes) -> None:
        received.append((routing_key, body))

    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.NONE)
    try:
        await bus.listen(topic=case.topic, listener=listener)
        for stream, routing_key in (
            (events_stream, "refresh.registry.branches"),
            (rpcs_stream, "send.echo.request"),
            (events_stream, "refresh.git.fetch"),
        ):
            await redis_api.publish_message(stream=stream, routing_key=routing_key, body='{"listened": true}')
        await wait_until(lambda: len(received) == len(case.expected))
    finally:
        await bus.shutdown()

    delivered = await conn.xreadgroup(
        groupname=RedisMessageBus.RPCS_GROUP, consumername="worker", streams={rpcs_stream: ">"}, count=10
    )
    assert sorted(received) == [(routing_key, b'{"listened": true}') for routing_key in case.expected]
    assert isinstance(delivered, list)
    assert [_as_text(fields["routing_key"]) for _stream, entries in delivered for _entry_id, fields in entries] == [
        "send.echo.request"
    ]


async def test_redis_running_work_item_is_not_claimed_again(redis_api: RedisManager) -> None:
    """A worker keeps marking the work item it is handling, so the claim passes leave it alone while it runs."""
    conn = await redis_api.get_connection()
    rpcs_stream = f"{redis_api.namespace}:rpcs"
    handler = BlockingHandler()

    with patch("infrahub.services.adapters.message_bus.redis.execute_message", handler):
        api_bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
        git_bus = RedisMessageBus(settings=redis_api.settings, component_type=ComponentType.GIT_AGENT)
        git_bus.CLAIM_IDLE_MS = 1_000
        git_bus.IN_PROGRESS_REFRESH_SECONDS = 0.2
        git_bus.MAINTENANCE_INTERVAL = 0.3
        try:
            await git_bus._initialize()
            await api_bus.send(message=messages.SendEchoRequest(message="long running"))
            await wait_until(lambda: len(handler.started) == 1)
            # Several claim passes run while the handler takes longer than the claim threshold.
            await asyncio.sleep(git_bus.CLAIM_IDLE_MS * 3 / 1000)
            started_while_running = len(handler.started)
            pending = await conn.xpending_range(rpcs_stream, RedisMessageBus.RPCS_GROUP, min="-", max="+", count=10)
        finally:
            handler.release.set()
            await git_bus.shutdown()
            await api_bus.shutdown()

    assert started_while_running == 1
    assert [entry["times_delivered"] for entry in pending] == [1]


async def test_redis_work_item_interrupted_by_a_shutdown_is_taken_over_at_once(redis_api: RedisManager) -> None:
    """A worker that shuts down mid-task leaves the work item to the next worker's first claim pass."""
    conn = await redis_api.get_connection()
    rpcs_stream = f"{redis_api.namespace}:rpcs"
    handler = BlockingHandler()

    with patch("infrahub.services.adapters.message_bus.redis.execute_message", handler):
        api_bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
        first_worker = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.GIT_AGENT)
        try:
            await api_bus.send(message=messages.SendEchoRequest(message="interrupted"))
            await wait_until(lambda: len(handler.started) == 1)
        finally:
            await first_worker.shutdown()
        handler.release.set()

        # A second process, so a second consumer of the group.
        with patch("infrahub.services.adapters.message_bus.redis.WORKER_IDENTITY", "second-worker"):
            second_worker = await RedisMessageBus.new(
                settings=redis_api.settings, component_type=ComponentType.GIT_AGENT
            )
        try:
            await wait_until(lambda: len(handler.started) == 2)

            async def acknowledged() -> bool:
                summary = await conn.xpending(rpcs_stream, RedisMessageBus.RPCS_GROUP)
                return summary["pending"] == 0

            await wait_until(acknowledged)
        finally:
            await second_worker.shutdown()
            await api_bus.shutdown()

    assert handler.started == ["send.echo.request", "send.echo.request"]


@dataclass
class RedeliveryCase:
    name: str
    previous_deliveries: int
    parked: bool


@pytest.mark.parametrize(
    "case",
    [
        RedeliveryCase(
            name="last_allowed_delivery", previous_deliveries=RedisMessageBus.WORK_MAX_DELIVERIES - 1, parked=False
        ),
        RedeliveryCase(
            name="one_delivery_too_many", previous_deliveries=RedisMessageBus.WORK_MAX_DELIVERIES, parked=True
        ),
    ],
    ids=lambda case: case.name,
)
async def test_redis_work_item_delivered_too_often_is_parked(
    case: RedeliveryCase, redis_api: RedisManager, fake_log: FakeLogger
) -> None:
    """A claimed work item already delivered the maximum number of times goes to the dead-letter list instead."""
    api_bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    try:
        await api_bus.send(message=messages.SendEchoRequest(message="crashes its worker"))
    finally:
        await api_bus.shutdown()

    conn = await redis_api.get_connection()
    rpcs_stream = f"{redis_api.namespace}:rpcs"
    dead_letter = f"{redis_api.namespace}:rpcs:dead"
    delivered = await conn.xreadgroup(
        groupname=RedisMessageBus.RPCS_GROUP, consumername="crashed-worker", streams={rpcs_stream: ">"}, count=1
    )
    assert isinstance(delivered, list)
    entry_id = delivered[0][1][0][0]
    # Records the deliveries of earlier workers that stopped while handling the entry.
    await conn.xclaim(
        rpcs_stream,
        RedisMessageBus.RPCS_GROUP,
        "crashed-worker",
        min_idle_time=0,
        message_ids=[entry_id],
        retrycount=case.previous_deliveries,
        justid=True,
    )

    async def entry_settled() -> bool:
        summary = await conn.xpending(rpcs_stream, RedisMessageBus.RPCS_GROUP)
        return summary["pending"] == 0

    git_bus = RedisMessageBus(settings=redis_api.settings, component_type=ComponentType.GIT_AGENT)
    git_bus.CLAIM_IDLE_MS = 0
    with (
        patch("infrahub.services.adapters.message_bus.redis.get_logger", return_value=fake_log),
        patch("infrahub.message_bus.operations.send.echo.get_logger", return_value=fake_log),
    ):
        try:
            await git_bus._initialize()
            await wait_until(entry_settled)
        finally:
            await git_bus.shutdown()

    dead_entries = [ujson.loads(member) for member in await conn.lrange(dead_letter, 0, -1)]
    assert ("Received message: crashes its worker" in fake_log.info_logs) is not case.parked
    if case.parked:
        assert [(entry["id"], entry["deliveries"]) for entry in dead_entries] == [
            (entry_id, RedisMessageBus.WORK_MAX_DELIVERIES + 1)
        ]
        assert dead_entries[0]["fields"]["routing_key"] == "send.echo.request"
    else:
        assert dead_entries == []


async def test_redis_busy_worker_claims_an_abandoned_work_item_only_once_a_handler_slot_is_free(
    redis_api: RedisManager,
) -> None:
    """A worker whose handler slots are all taken leaves the other abandoned work items with their owner."""
    settings = redis_api.settings.model_copy(update={"maximum_concurrent_messages": 1})
    conn = await redis_api.get_connection()
    rpcs_stream = f"{redis_api.namespace}:rpcs"
    handler = BlockingHandler()

    api_bus = await RedisMessageBus.new(settings=settings, component_type=ComponentType.API_SERVER)
    try:
        for index in range(2):
            await api_bus.send(message=messages.SendEchoRequest(message=f"abandoned {index}"))
    finally:
        await api_bus.shutdown()
    await conn.xreadgroup(
        groupname=RedisMessageBus.RPCS_GROUP, consumername="dead-worker", streams={rpcs_stream: ">"}, count=2
    )

    async def owners() -> list[str]:
        pending = await conn.xpending_range(rpcs_stream, RedisMessageBus.RPCS_GROUP, min="-", max="+", count=10)
        return sorted(str(entry["consumer"]) for entry in pending)

    with patch("infrahub.services.adapters.message_bus.redis.execute_message", handler):
        git_bus = RedisMessageBus(settings=settings, component_type=ComponentType.GIT_AGENT)
        git_bus.CLAIM_IDLE_MS = 0
        try:
            await git_bus._initialize()
            await wait_until(lambda: len(handler.started) == 1)
            owners_while_busy = await owners()
            handler.release.set()
            await wait_until(lambda: len(handler.started) == 2)
        finally:
            handler.release.set()
            await git_bus.shutdown()

    assert owners_while_busy == ["dead-worker", f"git-worker-{WORKER_IDENTITY}"]


async def test_redis_work_item_whose_handling_raised_is_run_again(
    redis_api: RedisManager, fake_log: FakeLogger
) -> None:
    """A work item whose handling raised, as when its retry cannot be scheduled, stays pending and runs again."""
    conn = await redis_api.get_connection()
    rpcs_stream = f"{redis_api.namespace}:rpcs"
    attempts: list[str] = []

    async def fails_once(routing_key: str, message_body: bytes, message_bus: RedisMessageBus) -> None:
        attempts.append(routing_key)
        if len(attempts) == 1:
            raise redis.ResponseError("OOM command not allowed when used memory > 'maxmemory'.")

    async def acknowledged() -> bool:
        summary = await conn.xpending(rpcs_stream, RedisMessageBus.RPCS_GROUP)
        return summary["pending"] == 0

    with (
        patch("infrahub.services.adapters.message_bus.redis.execute_message", fails_once),
        patch("infrahub.services.adapters.message_bus.redis.get_logger", return_value=fake_log),
    ):
        api_bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
        git_bus = RedisMessageBus(settings=redis_api.settings, component_type=ComponentType.GIT_AGENT)
        git_bus.CLAIM_IDLE_MS = 500
        git_bus.MAINTENANCE_INTERVAL = 0.2
        try:
            await git_bus._initialize()
            await api_bus.send(message=messages.SendEchoRequest(message="fails once"))
            await wait_until(lambda: len(attempts) == 2)
            await wait_until(acknowledged)
        finally:
            await git_bus.shutdown()
            await api_bus.shutdown()

    assert attempts == ["send.echo.request", "send.echo.request"]
    assert "Error processing message" in fake_log.exception_logs


async def test_redis_missing_group_that_cannot_be_recreated_is_tried_again_after_a_pause(
    redis_api: RedisManager, fake_log: FakeLogger
) -> None:
    """A worker whose consumer group is gone and cannot be created again waits before its next attempt."""
    conn = await redis_api.get_connection()
    rpcs_stream = f"{redis_api.namespace}:rpcs"
    refused = AsyncMock(side_effect=redis.ResponseError("NOPERM this user has no permissions to run 'xgroup|create'"))

    git_bus = RedisMessageBus(settings=redis_api.settings, component_type=ComponentType.GIT_AGENT)
    git_bus.ERROR_BACKOFF_SECONDS = 60.0
    with patch("infrahub.services.adapters.message_bus.redis.get_logger", return_value=fake_log):
        try:
            await git_bus._initialize()
            with patch.object(git_bus, "_create_stream_and_group", refused):
                await conn.xgroup_destroy(rpcs_stream, RedisMessageBus.RPCS_GROUP)
                await wait_until(lambda: refused.await_count >= 1)
                # Several reads would pass in this time without the pause.
                await asyncio.sleep(RedisMessageBus.READ_BLOCK_MS / 1000)
                attempts = refused.await_count
        finally:
            await git_bus.shutdown()

    assert attempts == 1
    assert "Failed to recreate the stream or consumer group" in fake_log.exception_logs


async def test_redis_shutdown_cancels_a_handler_started_while_the_consumers_stop(redis_api: RedisManager) -> None:
    """A handler that a consumer starts while the shutdown stops that consumer is cancelled with the other handlers."""
    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.NONE)
    started_handlers: list[asyncio.Task] = []

    async def runs_until_cancelled(message_data: dict) -> None:
        await asyncio.Event().wait()

    subscription = StreamSubscription(
        stream=f"{redis_api.namespace}:unused", consumer="test", callback=runs_until_cancelled
    )

    async def starts_a_handler_when_stopped() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            bus._start_handler(b"1-0", {}, subscription, slots=None)
            started_handlers.extend(bus._handler_tasks)

    try:
        bus._consumer_tasks.append(asyncio.create_task(starts_a_handler_when_stopped()))
        # Lets the consumer start, so that its cancellation runs the block that starts the handler.
        await asyncio.sleep(0)
    finally:
        await bus.shutdown()

    assert len(started_handlers) == 1
    assert started_handlers[0].cancelled()
