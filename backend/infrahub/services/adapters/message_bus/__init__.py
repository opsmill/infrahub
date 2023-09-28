from typing import Optional

from infrahub.message_bus import InfrahubBaseMessage
from infrahub.message_bus.types import MessageTTL


class InfrahubMessageBus:
    async def publish(self, message: InfrahubBaseMessage, routing_key: str, delay: Optional[MessageTTL] = None) -> None:
        raise NotImplementedError()

    async def reply(self, message: InfrahubBaseMessage, routing_key: str) -> None:
        raise NotImplementedError()
