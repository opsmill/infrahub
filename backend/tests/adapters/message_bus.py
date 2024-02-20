from collections import defaultdict
from typing import Dict, List, Optional, Type, TypeVar

import ujson
from infrahub_sdk import UUIDT

from infrahub.components import ComponentType
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import build_component_registry
from infrahub.message_bus import InfrahubMessage, Meta
from infrahub.message_bus.messages import ROUTING_KEY_MAP
from infrahub.message_bus.operations import execute_message
from infrahub.message_bus.types import MessageTTL
from infrahub.services import InfrahubServices
from infrahub.services.adapters.message_bus import InfrahubMessageBus

ResponseClass = TypeVar("ResponseClass")


class BusRecorder(InfrahubMessageBus):
    def __init__(self, component_type: Optional[ComponentType] = None):
        self.messages: List[InfrahubMessage] = []
        self.messages_per_routing_key: Dict[str, List[InfrahubMessage]] = {}

    async def publish(self, message: InfrahubMessage, routing_key: str, delay: Optional[MessageTTL] = None) -> None:
        self.messages.append(message)
        if routing_key not in self.messages_per_routing_key:
            self.messages_per_routing_key[routing_key] = []
        self.messages_per_routing_key[routing_key].append(message)

    @property
    def seen_routing_keys(self) -> List[str]:
        return list(self.messages_per_routing_key.keys())


class BusSimulator(InfrahubMessageBus):
    def __init__(self, database: Optional[InfrahubDatabase] = None):
        self.messages: List[InfrahubMessage] = []
        self.messages_per_routing_key: Dict[str, List[InfrahubMessage]] = {}
        self.service: InfrahubServices = InfrahubServices(database=database, message_bus=self)
        self.replies: Dict[str, List[InfrahubMessage]] = defaultdict(list)
        build_component_registry()

    async def publish(self, message: InfrahubMessage, routing_key: str, delay: Optional[MessageTTL] = None) -> None:
        self.messages.append(message)
        if routing_key not in self.messages_per_routing_key:
            self.messages_per_routing_key[routing_key] = []
        self.messages_per_routing_key[routing_key].append(message)
        await execute_message(routing_key=routing_key, message_body=message.body, service=self.service)

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        correlation_id = message.meta.correlation_id or "default"
        self.replies[correlation_id].append(message)

    async def rpc(self, message: InfrahubMessage, response_class: Type[ResponseClass]) -> ResponseClass:
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
    def seen_routing_keys(self) -> List[str]:
        return list(self.messages_per_routing_key.keys())
