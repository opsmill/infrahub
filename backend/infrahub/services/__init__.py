from typing import Optional

from infrahub.exceptions import InitializationError
from infrahub.message_bus import InfrahubBaseMessage
from infrahub.message_bus.messages import ROUTING_KEY_MAP
from infrahub_client import InfrahubClient

from .adapters.database import InfrahubDatabase
from .adapters.message_bus import InfrahubMessageBus


class InfrahubServices:
    def __init__(
        self,
        client: Optional[InfrahubClient] = None,
        database: Optional[InfrahubDatabase] = None,
        message_bus: Optional[InfrahubMessageBus] = None,
    ):
        self._client = client
        self.database = database or InfrahubDatabase()
        self.message_bus = message_bus or InfrahubMessageBus()

    @property
    def client(self) -> InfrahubClient:
        if not self._client:
            raise InitializationError()

        return self._client

    async def send(self, message: InfrahubBaseMessage) -> None:
        routing_key = ROUTING_KEY_MAP.get(type(message))
        if not routing_key:
            raise ValueError("Unable to determine routing key")
        await self.message_bus.publish(message, routing_key=routing_key)
