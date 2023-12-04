from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from aio_pika.abc import AbstractExchange

    from infrahub.message_bus import InfrahubMessage, InfrahubResponse
    from infrahub.message_bus.types import MessageTTL
    from infrahub.services import InfrahubServices


class InfrahubMessageBus:
    # This exchange attribute should be removed when the InfrahubRpcClient
    # class has been removed
    rpc_exchange: Optional[AbstractExchange] = None

    async def initialize(self, service: InfrahubServices) -> None:
        """Initialize the Message bus"""

    async def publish(self, message: InfrahubMessage, routing_key: str, delay: Optional[MessageTTL] = None) -> None:
        raise NotImplementedError()

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        raise NotImplementedError()

    async def rpc(self, message: InfrahubMessage) -> InfrahubResponse:
        raise NotImplementedError()
