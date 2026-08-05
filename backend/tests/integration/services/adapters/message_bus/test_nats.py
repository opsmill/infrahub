from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING
from unittest.mock import patch

import nats
import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

from infrahub import config
from infrahub.components import ComponentType
from infrahub.exceptions import RPCError
from infrahub.message_bus import messages
from infrahub.message_bus.messages.send_echo_request import SendEchoRequestResponse
from infrahub.services.adapters.message_bus.nats import NATSMessageBus
from infrahub.workers.dependencies import build_message_bus
from tests.helpers.constants import INFRAHUB_USE_TEST_CONTAINERS, PORT_NATS
from tests.helpers.utils import get_exposed_port

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fast_depends import Provider

    from infrahub.config import BrokerSettings
    from tests.adapters.log import FakeLogger

NATS_IMAGE = "nats:2.10.14-alpine"


@dataclass
class StreamInfo:
    """Information about a JetStream stream."""

    name: str
    subjects: list[str]
    messages: int


@dataclass
class ConsumerInfo:
    """Information about a JetStream consumer."""

    name: str
    filter_subjects: list[str]


@dataclass
class NatsManager:
    """Helper class for managing NATS resources during tests."""

    settings: BrokerSettings
    _connection: nats.NATS | None = None

    async def get_connection(self) -> nats.NATS:
        if self._connection is None or self._connection.is_closed:
            self._connection = await nats.connect(f"nats://{self.settings.address}:{self.settings.service_port}")
        return self._connection

    async def cleanup(self) -> None:
        """Delete every JetStream stream so each test starts from a clean server."""
        conn = await self.get_connection()
        jetstream = conn.jetstream()
        for stream in await jetstream.streams_info():
            await jetstream.delete_stream(stream.config.name)

    async def close(self) -> None:
        if self._connection and not self._connection.is_closed:
            await self._connection.drain()
            self._connection = None

    async def get_streams(self) -> dict[str, StreamInfo]:
        conn = await self.get_connection()
        jetstream = conn.jetstream()
        return {
            info.config.name: StreamInfo(
                name=info.config.name,
                subjects=list(info.config.subjects or []),
                messages=info.state.messages,
            )
            for info in await jetstream.streams_info()
        }

    async def get_consumers(self, stream: str) -> dict[str, ConsumerInfo]:
        conn = await self.get_connection()
        jetstream = conn.jetstream()
        consumers = {}
        for info in await jetstream.consumers_info(stream):
            filters = info.config.filter_subjects or (
                [info.config.filter_subject] if info.config.filter_subject else []
            )
            consumers[info.name] = ConsumerInfo(name=info.name, filter_subjects=list(filters))
        return consumers


@pytest.fixture(scope="module")
def nats_container(request: pytest.FixtureRequest, load_settings_before_session: None) -> dict[int, int] | None:
    if not INFRAHUB_USE_TEST_CONTAINERS:
        return None

    container = DockerContainer(image=NATS_IMAGE).with_command("-js").with_exposed_ports(PORT_NATS)
    container.start()
    wait_for_logs(container, "Server is ready")
    request.addfinalizer(container.stop)

    return {PORT_NATS: get_exposed_port(container, PORT_NATS)}


@pytest.fixture
async def nats_api(nats_container: dict[int, int] | None) -> AsyncGenerator[NatsManager, None]:
    """Fixture that provides a NatsManager for testing."""
    if nats_container is None:
        pytest.skip("Requires test containers")

    settings = deepcopy(config.SETTINGS.broker)
    settings.namespace = "integration-tests"
    settings.driver = config.BrokerDriver.NATS
    settings.address = "localhost"
    settings.port = nats_container[PORT_NATS]
    settings.username = ""
    settings.password = ""

    manager = NatsManager(settings=settings)
    await manager.cleanup()
    yield manager
    await manager.cleanup()
    await manager.close()


async def test_nats_initial_setup(nats_api: NatsManager) -> None:
    """Validates creation of streams and consumer configuration."""
    bus = await NATSMessageBus.new(settings=nats_api.settings, component_type=ComponentType.API_SERVER)
    api_streams = await nats_api.get_streams()
    await bus.shutdown()

    bus = await NATSMessageBus.new(settings=nats_api.settings, component_type=ComponentType.GIT_AGENT)
    rpcs_consumers = await nats_api.get_consumers(f"{nats_api.settings.namespace}-rpcs")
    await bus.shutdown()

    # Events stream covers both regular and broadcasted event bindings
    events_stream = api_streams.get(f"{nats_api.settings.namespace}-events")
    assert events_stream is not None
    assert sorted(events_stream.subjects) == sorted(
        NATSMessageBus.event_bindings + NATSMessageBus.broadcasted_event_bindings
    )

    # Work queue covers the worker bindings
    rpcs_stream = api_streams.get(f"{nats_api.settings.namespace}-rpcs")
    assert rpcs_stream is not None
    assert sorted(rpcs_stream.subjects) == sorted(NATSMessageBus.worker_bindings)

    # RPC replies flow through core NATS inboxes; no per-worker stream is created
    assert sorted(api_streams) == [
        f"{nats_api.settings.namespace}-events",
        f"{nats_api.settings.namespace}-rpcs",
    ]

    # The work queue consumer receives work items, not events
    assert sorted(rpcs_consumers["git-workers"].filter_subjects) == sorted(NATSMessageBus.worker_bindings)


async def test_nats_on_message(nats_api: NatsManager, fake_log: FakeLogger) -> None:
    """Validates that work queue messages are delivered to and executed by a git worker."""
    api_bus = await NATSMessageBus.new(settings=nats_api.settings, component_type=ComponentType.API_SERVER)
    git_bus = await NATSMessageBus.new(settings=nats_api.settings, component_type=ComponentType.GIT_AGENT)

    with patch("infrahub.message_bus.operations.send.echo.get_logger", return_value=fake_log):
        await api_bus.send(message=messages.SendEchoRequest(message="Hello there"))
        for _ in range(50):
            if fake_log.info_logs:
                break
            await asyncio.sleep(delay=0.2)
        await git_bus.shutdown()
        await api_bus.shutdown()

    assert fake_log.info_logs == ["Received message: Hello there"]
    assert fake_log.error_logs == []


async def test_nats_on_message_invalid_routing_key(nats_api: NatsManager, fake_log: FakeLogger) -> None:
    """Validates logging of invalid routing key on the work queue."""
    bus = await NATSMessageBus.new(settings=nats_api.settings, component_type=ComponentType.GIT_AGENT)

    with patch("infrahub.services.adapters.message_bus.nats.get_logger", return_value=fake_log):
        await bus.publish(
            routing_key="request.something.invalid", message=messages.SendEchoRequest(message="Hello there")
        )
        for _ in range(50):
            if fake_log.error_logs:
                break
            await asyncio.sleep(delay=0.2)
        await bus.shutdown()

    assert fake_log.info_logs == []
    assert fake_log.error_logs == ["Invalid message received"]


async def test_nats_event_broadcast(nats_api: NatsManager, fake_log: FakeLogger) -> None:
    """Validates that events are delivered to every worker, including the publisher."""
    api_bus = await NATSMessageBus.new(settings=nats_api.settings, component_type=ComponentType.API_SERVER)
    git_bus = await NATSMessageBus.new(settings=nats_api.settings, component_type=ComponentType.GIT_AGENT)

    with patch("infrahub.services.adapters.message_bus.nats.get_logger", return_value=fake_log):
        await api_bus.publish(
            message=messages.SendEchoRequest(message="broadcast"), routing_key="refresh.registry.invalid"
        )
        for _ in range(50):
            if len(fake_log.error_logs) >= 2:
                break
            await asyncio.sleep(delay=0.2)
        await api_bus.shutdown()
        await git_bus.shutdown()

    assert fake_log.error_logs == ["Invalid message received", "Invalid message received"]


async def test_nats_event_binding_filter(nats_api: NatsManager, fake_log: FakeLogger) -> None:
    """Validates that refresh.git.* events publish successfully and only reach git workers."""
    api_bus = await NATSMessageBus.new(settings=nats_api.settings, component_type=ComponentType.API_SERVER)
    git_bus = await NATSMessageBus.new(settings=nats_api.settings, component_type=ComponentType.GIT_AGENT)

    with patch("infrahub.services.adapters.message_bus.nats.get_logger", return_value=fake_log):
        await api_bus.publish(message=messages.SendEchoRequest(message="git only"), routing_key="refresh.git.invalid")
        for _ in range(50):
            if fake_log.error_logs:
                break
            await asyncio.sleep(delay=0.2)
        # Allow a spurious second delivery to surface before asserting
        await asyncio.sleep(delay=0.5)
        await api_bus.shutdown()
        await git_bus.shutdown()

    assert fake_log.error_logs == ["Invalid message received"]


async def test_nats_rpc(nats_api: NatsManager, fake_log: FakeLogger, dependency_provider: Provider) -> None:
    """Validates that RPC messages work correctly."""
    api_bus = await NATSMessageBus.new(settings=nats_api.settings, component_type=ComponentType.API_SERVER)
    git_bus = await NATSMessageBus.new(settings=nats_api.settings, component_type=ComponentType.GIT_AGENT)

    with dependency_provider.scope(build_message_bus, lambda: git_bus):
        try:
            response = await api_bus.rpc(
                message=messages.SendEchoRequest(message="You can reply to this message"),
                response_class=SendEchoRequestResponse,
                timeout=10,
            )
            assert response.data.response == "Reply to: You can reply to this message"
        finally:
            await git_bus.shutdown()
            await api_bus.shutdown()


async def test_nats_rpc_timeout(nats_api: NatsManager) -> None:
    """Validates that an RPC call fails cleanly when no worker replies."""
    bus = await NATSMessageBus.new(settings=nats_api.settings, component_type=ComponentType.API_SERVER)

    with pytest.raises(RPCError) as exc:
        await bus.rpc(
            message=messages.SendEchoRequest(message="nobody is listening"),
            response_class=SendEchoRequestResponse,
            timeout=1,
        )

    assert exc.value.message == "No response to RPC message 'SendEchoRequest' within 1s"
    assert bus.futures == {}
    await bus.shutdown()
