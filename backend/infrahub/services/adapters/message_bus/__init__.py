from typing import Optional

from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.types import MessageTTL


class InfrahubMessageBus:
    async def publish(self, message: InfrahubMessage, routing_key: str, delay: Optional[MessageTTL] = None) -> None:
        raise NotImplementedError()

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        raise NotImplementedError()
