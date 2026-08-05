from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
import redis.asyncio as redis
import ujson

from infrahub import config
from infrahub.components import ComponentType
from infrahub.exceptions import RPCError
from infrahub.message_bus import messages
from infrahub.message_bus.messages.send_echo_request import SendEchoRequestResponse
from infrahub.message_bus.operations import execute_message
from infrahub.message_bus.types import MessageTTL
from infrahub.services import InfrahubServices
from infrahub.services.adapters.message_bus.redis import RedisMessageBus
from infrahub.worker import WORKER_IDENTITY
from infrahub.workers.dependencies import build_message_bus

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fast_depends import Provider

    from infrahub.config import BrokerSettings
    from tests.adapters.log import FakeLogger


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
            ssl_context = None
            if self.settings.tls_enabled:
                import ssl

                ssl_context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
                if self.settings.tls_ca_file:
                    ssl_context.load_verify_locations(cafile=self.settings.tls_ca_file)
                if self.settings.tls_insecure:
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE

            self._connection = redis.Redis(
                host=self.settings.address,
                port=self.settings.service_port,
                username=self.settings.username or None,
                password=self.settings.password or None,
                ssl=ssl_context if self.settings.tls_enabled else False,
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
                    streams.append(StreamInfo(name=key, length=length, groups=group_names))
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
            return [{"id": entry_id, "data": data} for entry_id, data in entries]
        except redis.ResponseError:
            return []

    async def publish_message(self, stream: str, routing_key: str, body: str, headers: dict | None = None) -> str:
        """Publish a message directly to a stream."""
        conn = await self.get_connection()
        return await conn.xadd(
            stream,
            {
                "routing_key": routing_key,
                "body": body,
                "headers": ujson.dumps(headers or {}),
            },
        )


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
    _ = await InfrahubServices.new(message_bus=bus, component_type=ComponentType.API_SERVER)

    api_streams = await redis_api.get_streams()
    await bus.shutdown()

    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.GIT_AGENT)
    _ = await InfrahubServices.new(message_bus=bus, component_type=ComponentType.GIT_AGENT)

    agent_rpcs_groups = await redis_api.get_consumer_groups(f"{redis_api.namespace}:rpcs")
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
    _ = await InfrahubServices.new(message_bus=bus, component_type=ComponentType.API_SERVER)

    normal_message = messages.SendEchoRequest(message="normal")

    await bus.send(message=normal_message)

    # Give time for message to be published
    await asyncio.sleep(0.1)

    rpcs_messages = await redis_api.get_stream_messages(f"{redis_api.namespace}:rpcs")
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
        # Publish before the consumer's first read to ensure no message published
        # right after stream creation is dropped.
        await redis_api.publish_message(
            stream=bus.callback_stream,
            routing_key="send.echo.request",
            body=echo_message.body.decode(),
        )
        await asyncio.sleep(delay=1)
        await service.shutdown()

    assert fake_log.info_logs == ["Received message: Hello there"]
    assert fake_log.error_logs == []


async def test_redis_callback_with_invalid_routing_key(redis_api: RedisManager, fake_log: FakeLogger) -> None:
    """Validate that messages with an invalid routing key are logged as errors."""
    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    service = await InfrahubServices.new(message_bus=bus, component_type=ComponentType.API_SERVER)

    # Publish an invalid message directly to the callback stream
    with patch("infrahub.services.adapters.message_bus.redis.get_logger", return_value=fake_log):
        await redis_api.publish_message(
            stream=bus.callback_stream,
            routing_key="event.branch.invalid",
            body="Completely invalid",
        )
        await asyncio.sleep(delay=3)
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
    """Consume and process RPC messages from the stream."""
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
            if not entries:
                continue
            for _stream_name, stream_entries in entries:
                for message_id, message_data in stream_entries:
                    await _process_rpc_entry(message_id, message_data, bus, redis_api)
        except asyncio.CancelledError:
            break
        except Exception:
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
        await bus.send(message=messages.SendEchoRequest(message="Hello there"))
        await asyncio.sleep(delay=1)
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
        await bus.publish(
            routing_key="request.something.invalid", message=messages.SendEchoRequest(message="Hello there")
        )
        await asyncio.sleep(delay=1)
        await bus.shutdown()

    assert fake_log.info_logs == []
    assert fake_log.error_logs == ["Invalid message received"]


async def test_redis_event_broadcast(redis_api: RedisManager, fake_log: FakeLogger) -> None:
    """Validates that events are delivered to every worker, including the publisher."""
    api_bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    git_bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.GIT_AGENT)

    with patch("infrahub.services.adapters.message_bus.redis.get_logger", return_value=fake_log):
        await api_bus.publish(
            message=messages.SendEchoRequest(message="broadcast"), routing_key="refresh.registry.invalid"
        )
        await asyncio.sleep(delay=1)
        await api_bus.shutdown()
        await git_bus.shutdown()

    assert fake_log.error_logs == ["Invalid message received", "Invalid message received"]


async def test_redis_event_binding_filter(redis_api: RedisManager, fake_log: FakeLogger) -> None:
    """Validates that workers ignore events outside their bindings."""
    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)

    with patch("infrahub.services.adapters.message_bus.redis.get_logger", return_value=fake_log):
        # refresh.git.* events are only bound by git workers, the API server must skip them
        await bus.publish(message=messages.SendEchoRequest(message="git only"), routing_key="refresh.git.invalid")
        await bus.publish(message=messages.SendEchoRequest(message="for api"), routing_key="refresh.registry.invalid")
        await asyncio.sleep(delay=1)
        await bus.shutdown()

    assert fake_log.error_logs == ["Invalid message received"]


async def test_redis_delayed_retry_republished(redis_api: RedisManager) -> None:
    """Validates that failed-message retries are re-published after their delay."""
    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    conn = await redis_api.get_connection()
    rpcs_stream = f"{redis_api.namespace}:rpcs"
    delayed_queue = f"{redis_api.namespace}:delayed"

    await bus.send(message=messages.SendEchoRequest(message="try again"), delay=MessageTTL.FIVE, is_retry=True)

    # The pending retry is durably recorded before the publish call returns
    assert await conn.zcard(delayed_queue) == 1
    assert await conn.xlen(rpcs_stream) == 0
    await asyncio.sleep(delay=6)
    assert await conn.xlen(rpcs_stream) == 1
    assert await conn.zcard(delayed_queue) == 0

    await bus.shutdown()


async def test_redis_delayed_retry_survives_publisher_shutdown(redis_api: RedisManager) -> None:
    """Validates that a pending retry outlives the worker that scheduled it."""
    publisher = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    conn = await redis_api.get_connection()
    rpcs_stream = f"{redis_api.namespace}:rpcs"

    await publisher.send(message=messages.SendEchoRequest(message="survivor"), delay=MessageTTL.FIVE, is_retry=True)
    await publisher.shutdown()

    assert await conn.zcard(f"{redis_api.namespace}:delayed") == 1

    other_worker = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    await asyncio.sleep(delay=6)
    await other_worker.shutdown()

    stream_messages = await redis_api.get_stream_messages(rpcs_stream)
    assert len(stream_messages) == 1
    delivered = messages.SendEchoRequest(**ujson.loads(stream_messages[0]["data"]["body"]))
    assert delivered.message == "survivor"
    assert stream_messages[0]["data"]["routing_key"] == "send.echo.request"


async def test_redis_delayed_delivery_isolates_bad_entries(redis_api: RedisManager, fake_log: FakeLogger) -> None:
    """Validates that an undeliverable delayed entry neither blocks nor duplicates the other entries."""
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

    with patch("infrahub.services.adapters.message_bus.redis.get_logger", return_value=fake_log):
        bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
        # Several delivery scans pass; re-delivery of the good entry would show up as extra stream entries
        await asyncio.sleep(delay=2.5)
        await bus.shutdown()

    assert await conn.xlen(good_stream) == 1
    assert set(await conn.zrange(delayed_queue, 0, -1)) == {poison_member, malformed_member}
    assert "Failed to deliver delayed messages, keeping them queued for retry" in fake_log.error_logs


async def test_redis_pending_messages_reclaimed(redis_api: RedisManager, fake_log: FakeLogger) -> None:
    """Validates that unacknowledged messages of dead consumers are re-processed."""
    api_bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    await api_bus.send(message=messages.SendEchoRequest(message="orphaned"))
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
    git_bus.DELIVER_TIMEOUT = 0  # claim immediately instead of after 30 minutes
    with patch("infrahub.message_bus.operations.send.echo.get_logger", return_value=fake_log):
        await git_bus._initialize()
        await asyncio.sleep(delay=1)
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

    with patch("infrahub.message_bus.operations.send.echo.get_logger", return_value=fake_log):
        await git_bus._initialize()
        for index in range(3):
            await api_bus.send(message=messages.SendEchoRequest(message=f"echo {index}"))
        await asyncio.sleep(delay=3)
        await git_bus.shutdown()
        await api_bus.shutdown()

    assert len(fake_log.info_logs) == 3
    assert fake_log.error_logs == []
    # Everything before the last delivered entry is trimmed away
    assert await conn.xlen(rpcs_stream) <= 1


async def test_redis_consumer_deregistered_on_shutdown(redis_api: RedisManager) -> None:
    """Validates that a worker removes its work queue consumer when shutting down."""
    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.GIT_AGENT)

    consumers: list[str] = []
    for _ in range(50):
        groups = await redis_api.get_consumer_groups(f"{redis_api.namespace}:rpcs")
        rpcs_group = next((g for g in groups if g.name == RedisMessageBus.RPCS_GROUP), None)
        if rpcs_group and rpcs_group.consumers:
            consumers = rpcs_group.consumers
            break
        await asyncio.sleep(delay=0.1)
    assert consumers == [f"git-worker-{WORKER_IDENTITY}"]

    await bus.shutdown()

    groups = await redis_api.get_consumer_groups(f"{redis_api.namespace}:rpcs")
    rpcs_group = next(g for g in groups if g.name == RedisMessageBus.RPCS_GROUP)
    assert rpcs_group.consumers == []


async def test_redis_callback_stream_capped(redis_api: RedisManager) -> None:
    """Validates that a callback stream does not grow without bound as replies accumulate."""
    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.GIT_AGENT)
    conn = await redis_api.get_connection()
    requester_callback_stream = f"{redis_api.namespace}:callback:other-worker"

    reply_count = RedisMessageBus.CALLBACK_STREAM_MAXLEN * 2
    for index in range(reply_count):
        await bus.reply(
            message=messages.SendEchoRequest(message=f"reply {index}"), routing_key=requester_callback_stream
        )

    length = await conn.xlen(requester_callback_stream)
    # Trimming is approximate: Redis keeps at least MAXLEN entries and removes
    # whole macro nodes (100 entries by default), so allow that much slack.
    assert RedisMessageBus.CALLBACK_STREAM_MAXLEN <= length <= RedisMessageBus.CALLBACK_STREAM_MAXLEN + 200

    await bus.shutdown()


async def test_redis_rpc_timeout(redis_api: RedisManager) -> None:
    """Validates that an RPC call fails cleanly when no worker replies."""
    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)

    with pytest.raises(RPCError) as exc:
        await bus.rpc(
            message=messages.SendEchoRequest(message="nobody is listening"),
            response_class=SendEchoRequestResponse,
            timeout=1,
        )

    assert exc.value.message == "No response to RPC message 'SendEchoRequest' within 1s"
    assert bus.futures == {}
    await bus.shutdown()
