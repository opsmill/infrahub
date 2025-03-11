from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, TypeVar

import ujson
from infrahub_sdk.uuidt import UUIDT

from infrahub.dependencies.registry import build_component_registry
from infrahub.message_bus import InfrahubMessage, Meta
from infrahub.message_bus.messages import ROUTING_KEY_MAP
from infrahub.message_bus.operations import execute_message
from infrahub.services.adapters.message_bus import InfrahubMessageBus

if TYPE_CHECKING:
    from infrahub.message_bus.types import MessageTTL

ResponseClass = TypeVar("ResponseClass")


class BusSimulator(InfrahubMessageBus):
    def __init__(self) -> None:
        self.messages: list[InfrahubMessage] = []
        self.messages_per_routing_key: dict[str, list[InfrahubMessage]] = {}
        self.replies: dict[str, list[InfrahubMessage]] = defaultdict(list)
        build_component_registry()

    async def publish(
        self,
        message: InfrahubMessage,
        routing_key: str,
        delay: MessageTTL | None = None,  # noqa: ARG002
        is_retry: bool = False,  # noqa: ARG002
    ) -> None:
        self.messages.append(message)
        if routing_key not in self.messages_per_routing_key:
            self.messages_per_routing_key[routing_key] = []
        self.messages_per_routing_key[routing_key].append(message)
        assert self.service is not None
        await execute_message(routing_key=routing_key, message_body=message.body, service=self.service)

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:  # noqa: ARG002
        correlation_id = message.meta.correlation_id or "default"
        self.replies[correlation_id].append(message)

    async def rpc(self, message: InfrahubMessage, response_class: type[ResponseClass]) -> ResponseClass:
        routing_key = ROUTING_KEY_MAP.get(type(message), "")

        correlation_id = str(UUIDT())
        message.meta = Meta(correlation_id=correlation_id, reply_to="ci-testing")

        await self.publish(message=message, routing_key=routing_key)
        reply_id = correlation_id or "default"
        assert len(self.replies[reply_id]) == 1
        response = self.replies[reply_id][0]
        data = ujson.loads(response.body)
        return response_class(**data)

    @property
    def seen_routing_keys(self) -> list[str]:
        return list(self.messages_per_routing_key.keys())
