from typing import Optional

from aio_pika.abc import AbstractChannel, AbstractExchange

from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.types import MessageTTL
from infrahub.services.adapters.message_bus import InfrahubMessageBus


class RabbitMQMessageBus(InfrahubMessageBus):
    def __init__(
        self, channel: AbstractChannel, exchange: AbstractExchange, delayed_exchange: AbstractExchange
    ) -> None:
        self.channel = channel
        self.exchange = exchange
        self.delayed_exchange = delayed_exchange

    async def publish(self, message: InfrahubMessage, routing_key: str, delay: Optional[MessageTTL] = None) -> None:
        if delay:
            message.assign_header(key="delay", value=delay.value)
            await self.delayed_exchange.publish(message, routing_key=routing_key)
        else:
            await self.exchange.publish(message, routing_key=routing_key)

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        await self.channel.default_exchange.publish(message, routing_key=routing_key)
