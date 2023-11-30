from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from infrahub import config
from infrahub.components import ComponentType
from infrahub.log import clear_log_context
from infrahub.message_bus import InfrahubMessage, get_broker, messages
from infrahub.message_bus.operations import execute_message
from infrahub.services.adapters.message_bus import InfrahubMessageBus
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractIncomingMessage

    from infrahub.message_bus.types import MessageTTL
    from infrahub.services import InfrahubServices


class RabbitMQMessageBus(InfrahubMessageBus):
    def __init__(
        self,
        component_type: ComponentType,
        channel: Optional[AbstractChannel] = None,
        exchange: Optional[AbstractExchange] = None,
        delayed_exchange: Optional[AbstractExchange] = None,
    ) -> None:
        self.channel: AbstractChannel
        self.exchange: AbstractExchange
        self.delayed_exchange: AbstractExchange
        self.service: InfrahubServices
        self.component_type = component_type
        if channel:
            self.channel = channel
        if exchange:
            self.exchange = exchange
        if delayed_exchange:
            self.delayed_exchange = delayed_exchange

    async def initialize(self, service: InfrahubServices) -> None:
        self.service = service
        if self.component_type == ComponentType.GIT_AGENT:
            await self._initialize_git_worker()

    async def on_callback(self, message: AbstractIncomingMessage) -> None:
        clear_log_context()
        if message.routing_key in messages.MESSAGE_MAP:
            await execute_message(routing_key=message.routing_key, message_body=message.body, service=self.service)

    async def _initialize_git_worker(self) -> None:
        connection = await get_broker()
        # Create a channel and subscribe to the incoming RPC queue
        self.channel = await connection.channel()
        events_queue = await self.channel.declare_queue(name=f"worker-events-{WORKER_IDENTITY}", exclusive=True)

        self.exchange = await self.channel.declare_exchange(
            f"{config.SETTINGS.broker.namespace}.events", type="topic", durable=True
        )
        await events_queue.bind(self.exchange, routing_key="refresh.registry.*")
        self.delayed_exchange = await self.channel.get_exchange(name=f"{config.SETTINGS.broker.namespace}.delayed")

        await events_queue.consume(callback=self.on_callback, no_ack=True)

        await self.channel.declare_queue(
            f"{config.SETTINGS.broker.namespace}.rpcs", durable=True, arguments={"x-queue-type": "quorum"}
        )

    async def publish(self, message: InfrahubMessage, routing_key: str, delay: Optional[MessageTTL] = None) -> None:
        if delay:
            message.assign_header(key="delay", value=delay.value)
            await self.delayed_exchange.publish(message, routing_key=routing_key)
        else:
            await self.exchange.publish(message, routing_key=routing_key)

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        await self.channel.default_exchange.publish(message, routing_key=routing_key)
