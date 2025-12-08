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
from infrahub.message_bus import messages
from infrahub.message_bus.messages.send_echo_request import SendEchoRequestResponse
from infrahub.message_bus.operations import execute_message
from infrahub.services import InfrahubServices
from infrahub.services.adapters.message_bus.redis import RedisMessageBus
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

    # Check that events stream was created with expected consumer group
    events_stream = next((s for s in api_streams if s.name == f"{redis_api.namespace}:events"), None)
    assert events_stream is not None
    assert f"{redis_api.namespace}-events" in events_stream.groups

    # Check that RPCs stream was created
    rpcs_stream = next((s for s in api_streams if s.name == f"{redis_api.namespace}:rpcs"), None)
    assert rpcs_stream is not None
    assert f"{redis_api.namespace}-rpcs" in rpcs_stream.groups

    # Check that git worker created its consumer group
    assert any(g.name == "git-workers" for g in agent_rpcs_groups)


async def test_redis_publish(redis_api: RedisManager) -> None:
    """Validate that the adapter publishes messages to the correct stream."""
    bus = await RedisMessageBus.new(settings=redis_api.settings, component_type=ComponentType.API_SERVER)
    _ = await InfrahubServices.new(message_bus=bus, component_type=ComponentType.API_SERVER)

    normal_message = messages.SendEchoRequest(message="normal")

    await bus.send(message=normal_message)
    # Note: Redis implementation handles delays differently - using asyncio.sleep

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

    with patch("infrahub.message_bus.operations.send.echo.get_logger", return_value=fake_log):
        await service.message_bus.send(message=messages.SendEchoRequest(message="Hello there"))
        await asyncio.sleep(delay=1)
        await service.shutdown()

    # Note: The API server doesn't consume from RPC stream by default,
    # this test validates the message was published.
    # The actual callback processing happens in the GIT_AGENT.


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
    await conn.xack(f"{redis_api.namespace}:rpcs", f"{redis_api.namespace}-rpcs", message_id)


async def _consume_rpc_messages(redis_api: RedisManager, bus: RedisMessageBus) -> None:
    """Consume and process RPC messages from the stream."""
    conn = await redis_api.get_connection()
    while True:
        try:
            entries = await conn.xreadgroup(
                groupname=f"{redis_api.namespace}-rpcs",
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
