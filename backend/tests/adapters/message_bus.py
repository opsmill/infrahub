from collections import defaultdict
from typing import Optional, TypeVar

import ujson
from infrahub_sdk.uuidt import UUIDT

from infrahub.components import ComponentType
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import build_component_registry
from infrahub.message_bus import InfrahubMessage, Meta
from infrahub.message_bus.messages import ROUTING_KEY_MAP
from infrahub.message_bus.operations import execute_message
from infrahub.message_bus.types import MessageTTL
from infrahub.services import InfrahubServices
from infrahub.services.adapters.message_bus import InfrahubMessageBus
from infrahub.services.adapters.workflow import InfrahubWorkflow

ResponseClass = TypeVar("ResponseClass")


class BusRecorder(InfrahubMessageBus):
    def __init__(self, component_type: Optional[ComponentType] = None) -> None:
        self.messages: list[InfrahubMessage] = []
        self.messages_per_routing_key: dict[str, list[InfrahubMessage]] = {}

    async def publish(
        self, message: InfrahubMessage, routing_key: str, delay: Optional[MessageTTL] = None, is_retry: bool = False
    ) -> None:
        self.messages.append(message)
        if routing_key not in self.messages_per_routing_key:
            self.messages_per_routing_key[routing_key] = []
        self.messages_per_routing_key[routing_key].append(message)

    @property
    def seen_routing_keys(self) -> list[str]:
        return list(self.messages_per_routing_key.keys())


class BusSimulator(InfrahubMessageBus):
    def __init__(self, database: InfrahubDatabase | None = None, workflow: InfrahubWorkflow | None = None) -> None:
        self.messages: list[InfrahubMessage] = []
        self.messages_per_routing_key: dict[str, list[InfrahubMessage]] = {}
        self.service: InfrahubServices = InfrahubServices(database=database, message_bus=self, workflow=workflow)
        self.replies: dict[str, list[InfrahubMessage]] = defaultdict(list)
        build_component_registry()

    async def publish(
        self, message: InfrahubMessage, routing_key: str, delay: Optional[MessageTTL] = None, is_retry: bool = False
    ) -> None:
        self.messages.append(message)
        if routing_key not in self.messages_per_routing_key:
            self.messages_per_routing_key[routing_key] = []
        self.messages_per_routing_key[routing_key].append(message)
        await execute_message(routing_key=routing_key, message_body=message.body, service=self.service, skip_flow=True)

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
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
