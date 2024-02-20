from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

import httpx
import pytest
from aio_pika import Message

from infrahub import config
from infrahub.components import ComponentType
from infrahub.message_bus import messages
from infrahub.message_bus.messages.send_echo_request import SendEchoRequestResponse
from infrahub.message_bus.operations import execute_message
from infrahub.message_bus.types import MessageTTL
from infrahub.services import InfrahubServices
from infrahub.services.adapters.message_bus.rabbitmq import RabbitMQMessageBus
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from aio_pika.abc import AbstractIncomingMessage

    from infrahub.config import BrokerSettings


@dataclass
class Binding:
    source: str
    destination: str
    destination_type: str
    routing_key: str
    arguments: dict


@dataclass
class Exchange:
    durable: bool
    exchange_type: str
    name: str


@dataclass
class Queue:
    name: str
    arguments: dict
    durable: bool
    exclusive: bool
    queue_type: str


@dataclass
class RabbitMQManager:
    settings: BrokerSettings
    retry_timeout: int = 15

    @property
    def base_url(self) -> str:
        scheme = "https" if self.settings.tls_enabled else "http"
        port = f"1{self.settings.service_port}"
        return f"{scheme}://{self.settings.address}:{port}/api"

    async def create_virtual_host(self) -> None:
        response = await self._request(method="PUT", url=f"{self.base_url}/vhosts/{self.settings.virtualhost}")
        assert response.status_code == 201

    async def get_bindings(self, prefix: str = "") -> list[Binding]:
        response = await self._request(method="GET", url=f"{self.base_url}/bindings/{self.settings.virtualhost}")
        return [
            Binding(
                source=entry["source"],
                destination=entry["destination"],
                destination_type=entry["destination_type"],
                routing_key=entry["routing_key"],
                arguments=entry["arguments"],
            )
            for entry in response.json()
        ]

    async def get_exchanges(self, prefix: str = "") -> list[Exchange]:
        response = await self._request(method="GET", url=f"{self.base_url}/exchanges/{self.settings.virtualhost}")
        assert response.status_code == 200
        return [
            Exchange(name=entry["name"], exchange_type=entry["type"], durable=entry["durable"])
            for entry in response.json()
            if entry["name"].startswith(prefix)
        ]

    async def get_queues(self, prefix: str = "") -> list[Queue]:
        response = await self._request(method="GET", url=f"{self.base_url}/queues/{self.settings.virtualhost}")
        return [
            Queue(
                name=entry["name"],
                queue_type=entry["type"],
                durable=entry["durable"],
                exclusive=entry["exclusive"],
                arguments=entry["arguments"],
            )
            for entry in response.json()
            if entry["name"].startswith(prefix)
        ]

    async def delete_virtual_host(self) -> None:
        response = await self._request(method="DELETE", url=f"{self.base_url}/vhosts/{self.settings.virtualhost}")
        assert response.status_code in {204, 404}

    async def _request(self, method: str, url: str, payload: Optional[dict] = None) -> httpx.Response:
        params: dict[str, Any] = {}
        if payload:
            params["json"] = payload
        headers = {"content-type": "application/json"}
        retry_counter = 0
        retry_request = True
        while retry_request:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        auth=(self.settings.username, self.settings.password),
                        **params,
                    )
                    retry_request = False
            except httpx.NetworkError:
                await asyncio.sleep(0.1)
                retry_counter += 0.1
                if retry_counter > self.retry_timeout:
                    raise
        return response


@pytest.fixture
async def rabbitmq_api() -> RabbitMQManager:
    settings = deepcopy(config.SETTINGS.broker)
    settings.virtualhost = "integration-tests"
    manager = RabbitMQManager(settings=settings)
    await manager.delete_virtual_host()
    await manager.create_virtual_host()
    return manager


async def test_rabbitmq_initial_setup(rabbitmq_api: RabbitMQManager) -> None:
    """Validates creation of exchanges, queues and bindings."""

    bus = RabbitMQMessageBus(settings=rabbitmq_api.settings)
    api_service = InfrahubServices(message_bus=bus, component_type=ComponentType.API_SERVER)
    agent_service = InfrahubServices(message_bus=bus, component_type=ComponentType.GIT_AGENT)
    await bus.initialize(service=api_service)
    api_exchanges = await rabbitmq_api.get_exchanges(prefix="infrahub")
    api_queues = await rabbitmq_api.get_queues()
    api_bindings = await rabbitmq_api.get_bindings()
    await bus.shutdown()

    await bus.initialize(service=agent_service)
    agent_queues = await rabbitmq_api.get_queues()
    agent_bindings = await rabbitmq_api.get_bindings()
    await bus.shutdown()

    assert Exchange(durable=True, exchange_type="headers", name="infrahub.delayed") in api_exchanges
    assert Exchange(durable=True, exchange_type="topic", name="infrahub.dlx") in api_exchanges
    assert Exchange(durable=True, exchange_type="topic", name="infrahub.events") in api_exchanges
    assert (
        Queue(
            name=f"api-callback-{WORKER_IDENTITY}",
            arguments={},
            durable=False,
            exclusive=True,
            queue_type="classic",
        )
        in api_queues
    )
    assert (
        Queue(
            name=f"api-events-{WORKER_IDENTITY}",
            arguments={},
            durable=False,
            exclusive=True,
            queue_type="classic",
        )
        in api_queues
    )
    assert (
        Queue(
            name="infrahub.delay.five_seconds",
            arguments={"x-dead-letter-exchange": "infrahub.dlx", "x-max-priority": 5, "x-message-ttl": 5000},
            durable=True,
            exclusive=False,
            queue_type="classic",
        )
        in api_queues
    )
    assert (
        Queue(
            name="infrahub.delay.ten_seconds",
            arguments={"x-dead-letter-exchange": "infrahub.dlx", "x-max-priority": 5, "x-message-ttl": 10000},
            durable=True,
            exclusive=False,
            queue_type="classic",
        )
        in api_queues
    )
    assert (
        Queue(
            name="infrahub.delay.twenty_seconds",
            arguments={"x-dead-letter-exchange": "infrahub.dlx", "x-max-priority": 5, "x-message-ttl": 20000},
            durable=True,
            exclusive=False,
            queue_type="classic",
        )
        in api_queues
    )
    assert (
        Queue(
            name="infrahub.rpcs", arguments={"x-max-priority": 5}, durable=True, exclusive=False, queue_type="classic"
        )
        in api_queues
    )
    assert (
        Queue(
            name=f"worker-events-{WORKER_IDENTITY}",
            arguments={},
            durable=False,
            exclusive=True,
            queue_type="classic",
        )
        in agent_queues
    )

    assert (
        Binding(
            source="",
            destination=f"api-callback-{WORKER_IDENTITY}",
            destination_type="queue",
            routing_key=f"api-callback-{WORKER_IDENTITY}",
            arguments={},
        )
        in api_bindings
    )
    assert (
        Binding(
            source="",
            destination=f"api-events-{WORKER_IDENTITY}",
            destination_type="queue",
            routing_key=f"api-events-{WORKER_IDENTITY}",
            arguments={},
        )
        in api_bindings
    )
    assert (
        Binding(
            source="infrahub.delayed",
            destination="infrahub.delay.five_seconds",
            destination_type="queue",
            routing_key="infrahub.delay.five_seconds",
            arguments={"delay": 5000, "x-match": "all"},
        )
        in api_bindings
    )
    assert (
        Binding(
            source="infrahub.delayed",
            destination="infrahub.delay.ten_seconds",
            destination_type="queue",
            routing_key="infrahub.delay.ten_seconds",
            arguments={"delay": 10000, "x-match": "all"},
        )
        in api_bindings
    )
    assert (
        Binding(
            source="infrahub.delayed",
            destination="infrahub.delay.twenty_seconds",
            destination_type="queue",
            routing_key="infrahub.delay.twenty_seconds",
            arguments={"delay": 20000, "x-match": "all"},
        )
        in api_bindings
    )
    assert (
        Binding(
            source="infrahub.dlx",
            destination="infrahub.rpcs",
            destination_type="queue",
            routing_key="check.*.*",
            arguments={},
        )
        in api_bindings
    )
    assert (
        Binding(
            source="infrahub.dlx",
            destination="infrahub.rpcs",
            destination_type="queue",
            routing_key="event.*.*",
            arguments={},
        )
        in api_bindings
    )
    assert (
        Binding(
            source="infrahub.dlx",
            destination="infrahub.rpcs",
            destination_type="queue",
            routing_key="finalize.*.*",
            arguments={},
        )
        in api_bindings
    )
    assert (
        Binding(
            source="infrahub.events",
            destination=f"worker-events-{WORKER_IDENTITY}",
            destination_type="queue",
            routing_key="refresh.registry.*",
            arguments={},
        )
        in agent_bindings
    )
    assert (
        Binding(
            source="",
            destination=f"worker-events-{WORKER_IDENTITY}",
            destination_type="queue",
            routing_key=f"worker-events-{WORKER_IDENTITY}",
            arguments={},
        )
        in agent_bindings
    )


async def test_rabbitmq_publish(rabbitmq_api: RabbitMQManager) -> None:
    """Validate that the adapter publishes messages to the correct queue"""

    bus = RabbitMQMessageBus(settings=rabbitmq_api.settings)
    service = InfrahubServices(message_bus=bus, component_type=ComponentType.API_SERVER)

    normal_message = messages.EventBranchCreate(branch="normal", branch_id=str(uuid4()), data_only=True)
    delayed_message = messages.EventBranchCreate(branch="delayed", branch_id=str(uuid4()), data_only=True)

    await bus.initialize(service=service)
    await service.send(message=normal_message)
    await service.send(message=delayed_message, delay=MessageTTL.FIVE)

    queue = await bus.channel.get_queue(name=f"{bus.settings.namespace}.rpcs")
    delayed_queue = await bus.channel.get_queue(name=f"{bus.settings.namespace}.delay.five_seconds")
    message_from_queue = await queue.get()
    delayed_message_from_queue = await delayed_queue.get()
    parsed_message = json.loads(message_from_queue.body)
    parsed_delayed_message = json.loads(delayed_message_from_queue.body)

    await bus.shutdown()

    parsed_message = messages.EventBranchCreate(**parsed_message)
    parsed_delayed_message = messages.EventBranchCreate(**parsed_delayed_message)

    # The priority isn't currently included in the header, reset it to show expected priority
    normal_message.meta.priority = 3
    delayed_message.meta.priority = 3
    parsed_delayed_message.meta.headers = {"delay": 5000}
    assert message_from_queue.priority == 5
    assert delayed_message_from_queue.priority == 5
    assert parsed_message == normal_message
    assert parsed_delayed_message == delayed_message


async def test_rabbitmq_callback(rabbitmq_api: RabbitMQManager, fake_log) -> None:
    """Validates that incoming messages gets parsed by the callback method."""

    bus = RabbitMQMessageBus(settings=rabbitmq_api.settings)
    service = InfrahubServices(message_bus=bus, component_type=ComponentType.API_SERVER, log=fake_log)

    await bus.initialize(service=service)

    queue = await bus.channel.get_queue(
        f"{bus.settings.namespace}.rpcs",
    )
    await queue.consume(bus.on_callback, no_ack=True)

    await service.send(message=messages.SendEchoRequest(message="Hello there"))
    await asyncio.sleep(delay=0.1)

    assert "Received message: Hello there" in fake_log.info_logs
    await service.shutdown()


async def test_rabbitmq_callback_with_invalid_routing_key(rabbitmq_api: RabbitMQManager, fake_log) -> None:
    """Validate that messages with an invalid routing key is logged."""

    bus = RabbitMQMessageBus(settings=rabbitmq_api.settings)
    service = InfrahubServices(message_bus=bus, component_type=ComponentType.API_SERVER, log=fake_log)

    await bus.initialize(service=service)

    queue = await bus.channel.get_queue(
        f"{bus.settings.namespace}.rpcs",
    )
    await queue.consume(bus.on_callback, no_ack=True)

    await bus.exchange.publish(Message(body="Completely invalid".encode()), routing_key="event.branch.invalid")
    await asyncio.sleep(delay=0.1)
    assert "Invalid message received" in fake_log.error_logs
    await service.shutdown()


async def test_rabbitmq_rpc(rabbitmq_api: RabbitMQManager, fake_log) -> None:
    """Validates that incoming messages gets parsed by the callback method."""

    bus = RabbitMQMessageBus(settings=rabbitmq_api.settings)
    service = InfrahubServices(message_bus=bus, component_type=ComponentType.API_SERVER, log=fake_log)

    await bus.initialize(service=service)

    queue = await bus.channel.get_queue(
        f"{bus.settings.namespace}.rpcs",
    )
    callback = partial(on_callback, service=service)
    await queue.consume(callback, no_ack=True)

    response = await bus.rpc(
        message=messages.SendEchoRequest(message="You can reply to this message"),
        response_class=SendEchoRequestResponse,
    )
    await service.shutdown()

    assert response.data.response == "Reply to: You can reply to this message"


async def on_callback(message: AbstractIncomingMessage, service: InfrahubServices) -> None:
    await execute_message(routing_key=message.routing_key or "", message_body=message.body, service=service)
