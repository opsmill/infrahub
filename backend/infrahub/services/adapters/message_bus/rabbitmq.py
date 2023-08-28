from aio_pika.abc import AbstractExchange

from infrahub.message_bus import InfrahubBaseMessage
from infrahub.services.adapters.message_bus import InfrahubMessageBus


class RabbitMQMessageBus(InfrahubMessageBus):
    def __init__(self, exchange: AbstractExchange) -> None:
        self.exchange = exchange

    async def publish(self, message: InfrahubBaseMessage, routing_key: str) -> None:
        await self.exchange.publish(message, routing_key=routing_key)
