from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, TypeVar

ResponseClass = TypeVar("ResponseClass")

if TYPE_CHECKING:
    from infrahub.message_bus import InfrahubMessage
    from infrahub.message_bus.types import MessageTTL
    from infrahub.services import InfrahubServices


class InfrahubMessageBus:
    DELIVER_TIMEOUT: int = 30
    worker_bindings: List[str] = [
        "check.*.*",
        "event.*.*",
        "finalize.*.*",
        "git.*.*",
        "refresh.webhook.*",
        "request.*.*",
        "send.*.*",
        "schema.*.*",
        "transform.*.*",
        "trigger.*.*",
    ]
    event_bindings: List[str] = ["refresh.registry.*"]

    async def initialize(self, service: InfrahubServices) -> None:
        """Initialize the Message bus"""

    async def shutdown(self) -> None:
        """Shutdown the Message bus"""

    async def publish(self, message: InfrahubMessage, routing_key: str, delay: Optional[MessageTTL] = None) -> None:
        raise NotImplementedError()

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        raise NotImplementedError()

    async def rpc(self, message: InfrahubMessage, response_class: type[ResponseClass]) -> ResponseClass:
        raise NotImplementedError()
