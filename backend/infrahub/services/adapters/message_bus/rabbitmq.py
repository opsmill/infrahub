from aio_pika.abc import AbstractChannel, AbstractExchange

from infrahub.message_bus import InfrahubBaseMessage
from infrahub.services.adapters.message_bus import InfrahubMessageBus


class RabbitMQMessageBus(InfrahubMessageBus):
    def __init__(self, channel: AbstractChannel, exchange: AbstractExchange) -> None:
        self.channel = channel
        self.exchange = exchange

    async def publish(self, message: InfrahubBaseMessage, routing_key: str) -> None:
        await self.exchange.publish(message, routing_key=routing_key)

    async def reply(self, message: InfrahubBaseMessage, routing_key: str) -> None:
        await self.channel.default_exchange.publish(message, routing_key=routing_key)
