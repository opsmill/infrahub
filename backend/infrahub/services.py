from aio_pika.abc import AbstractExchange

from infrahub.message_bus import InfrahubBaseMessage
from infrahub.message_bus.messages import ROUTING_KEY_MAP
from infrahub_client import InfrahubClient


class InfrahubServices:
    def __init__(self, client: InfrahubClient, exchange: AbstractExchange):
        self.client = client
        self.exchange = exchange

    async def send(self, message: InfrahubBaseMessage) -> None:
        routing_key = ROUTING_KEY_MAP.get(type(message))
        if not routing_key:
            raise ValueError("Unable to determine routing key")
        await self.exchange.publish(message, routing_key=routing_key)
