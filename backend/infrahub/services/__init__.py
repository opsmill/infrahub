from typing import Optional

from infrahub.exceptions import InitializationError
from infrahub.message_bus import InfrahubBaseMessage, InfrahubResponse, Meta
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

    async def reply(self, message: InfrahubResponse, initiator: InfrahubBaseMessage) -> None:
        message.meta = message.meta or Meta()
        if initiator.meta:
            message.meta.correlation_id = initiator.meta.correlation_id
            routing_key = initiator.meta.reply_to or ""
            await self.message_bus.reply(message, routing_key=routing_key)
