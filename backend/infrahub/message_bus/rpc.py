from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import TYPE_CHECKING, List, MutableMapping

from infrahub import config
from infrahub.database import InfrahubDatabase, get_db
from infrahub.log import clear_log_context, get_log_data, get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.operations import execute_message
from infrahub.services import InfrahubServices
from infrahub.services.adapters.message_bus.rabbitmq import RabbitMQMessageBus
from infrahub.worker import WORKER_IDENTITY
from infrahub_client import UUIDT

from . import InfrahubBaseMessage, InfrahubResponse, Meta, get_broker
from .messages import ROUTING_KEY_MAP
from .types import MessageTTL

if TYPE_CHECKING:
    from aio_pika.abc import (
        AbstractChannel,
        AbstractExchange,
        AbstractIncomingMessage,
        AbstractQueue,
        AbstractRobustConnection,
    )

log = get_logger()


class InfrahubRpcClientBase:
    connection: AbstractRobustConnection
    channel: AbstractChannel
    callback_queue: AbstractQueue
    events_queue: AbstractQueue
    loop: asyncio.AbstractEventLoop
    exchange: AbstractExchange
    delayed_exchange: AbstractExchange
    dlx: AbstractExchange

    def __init__(self) -> None:
        self.futures: MutableMapping[str, asyncio.Future] = {}
        self.loop = asyncio.get_running_loop()
        self.service: InfrahubServices = InfrahubServices()

    async def connect(self) -> InfrahubRpcClient:
        self.connection = await get_broker()

        if not self.connection:
            return self

        self.channel = await self.connection.channel()
        self.callback_queue = await self.channel.declare_queue(name=f"api-callback-{WORKER_IDENTITY}", exclusive=True)
        self.events_queue = await self.channel.declare_queue(name=f"api-events-{WORKER_IDENTITY}", exclusive=True)

        await self.callback_queue.consume(self.on_response, no_ack=True)
        await self.events_queue.consume(self.on_response, no_ack=True)
        self.exchange = await self.channel.declare_exchange(
            f"{config.SETTINGS.broker.namespace}.events", type="topic", durable=True
        )
        self.dlx = await self.channel.declare_exchange(
            f"{config.SETTINGS.broker.namespace}.dlx", type="topic", durable=True
        )

        queue = await self.channel.declare_queue(
            f"{config.SETTINGS.broker.namespace}.rpcs", durable=True, arguments={"x-queue-type": "quorum"}
        )

        worker_bindings = [
            "check.*.*",
            "event.*.*",
            "finalize.*.*",
            "git.*.*",
            "request.*.*",
            "transform.*.*",
            "trigger.*.*",
        ]
        self.delayed_exchange = await self.channel.declare_exchange(
            f"{config.SETTINGS.broker.namespace}.delayed", type="headers", durable=True
        )
        for routing_key in worker_bindings:
            await queue.bind(self.exchange, routing_key=routing_key)
            await queue.bind(self.dlx, routing_key=routing_key)

        for ttl in MessageTTL.variations():
            ttl_queue = await self.channel.declare_queue(
                f"{config.SETTINGS.broker.namespace}.delay.{ttl.name.lower()}_seconds",
                durable=True,
                arguments={
                    "x-dead-letter-exchange": self.dlx.name,
                    "x-message-ttl": ttl.value,
                    "x-queue-type": "quorum",
                },
            )
            await ttl_queue.bind(
                self.delayed_exchange,
                arguments={"x-match": "all", "delay": ttl.value},
            )

        await self.events_queue.bind(self.exchange, routing_key="refresh.registry.*")

        db = InfrahubDatabase(driver=await get_db())
        self.service = InfrahubServices(
            database=db,
            message_bus=RabbitMQMessageBus(
                channel=self.channel, exchange=self.exchange, delayed_exchange=self.delayed_exchange
            ),
        )

        return self

    async def on_response(self, message: AbstractIncomingMessage) -> None:
        if message.correlation_id:
            future: asyncio.Future = self.futures.pop(message.correlation_id)

            if future:
                future.set_result(message)
                return

        clear_log_context()
        if message.routing_key in messages.MESSAGE_MAP:
            await execute_message(routing_key=message.routing_key, message_body=message.body, service=self.service)
        else:
            log.error("Invalid message received", message=f"{message!r}")

    async def rpc(self, message: InfrahubBaseMessage) -> InfrahubResponse:
        correlation_id = str(UUIDT())

        future = self.loop.create_future()
        self.futures[correlation_id] = future

        log_data = get_log_data()
        request_id = log_data.get("request_id", "")
        message.meta = Meta(request_id=request_id, correlation_id=correlation_id, reply_to=self.callback_queue.name)

        await self.send(message=message)

        response = await future
        data = json.loads(response.body)
        return InfrahubResponse(**data)

    async def send(self, message: InfrahubBaseMessage) -> None:
        routing_key = ROUTING_KEY_MAP.get(type(message))

        if not routing_key:
            raise ValueError("Unable to determine routing key")

        log_data = get_log_data()
        request_id = log_data.get("request_id", "")
        message.meta = message.meta or Meta(request_id=request_id)
        await self.exchange.publish(message, routing_key=routing_key)


class InfrahubRpcClient(InfrahubRpcClientBase):
    pass


class InfrahubRpcClientTesting(InfrahubRpcClientBase):
    """InfrahubRPCClient instrumented for testing and mocking."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.responses = defaultdict(list)
        self.replies: List[InfrahubResponse] = []
        self.sent: List[InfrahubBaseMessage] = []

    async def connect(self) -> InfrahubRpcClient:
        return self

    async def rpc(self, message: InfrahubBaseMessage) -> InfrahubResponse:
        return self.replies.pop()

    async def add_mock_reply(self, response: InfrahubResponse) -> None:
        self.replies.append(response)

    async def send(self, message: InfrahubBaseMessage) -> None:
        self.sent.append(message)
