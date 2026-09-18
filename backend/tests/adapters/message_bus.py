import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar, cast

import ujson
from infrahub_sdk.uuidt import UUIDT

from infrahub.components import ComponentType
from infrahub.config import BrokerSettings
from infrahub.dependencies.registry import build_component_registry
from infrahub.message_bus import InfrahubMessage, Meta
from infrahub.message_bus.messages import ROUTING_KEY_MAP
from infrahub.message_bus.operations import execute_message
from infrahub.message_bus.types import MessageTTL
from infrahub.services.adapters.message_bus import InfrahubMessageBus
from infrahub.services.adapters.message_bus.nats import NATSMessageBus
from infrahub.services.adapters.message_bus.rabbitmq import RabbitMQMessageBus

if TYPE_CHECKING:
    from aio_pika.abc import AbstractQueue
    from nats.js.api import StreamInfo

ResponseClass = TypeVar("ResponseClass")


class BusRecorder(InfrahubMessageBus):
    def __init__(self) -> None:
        self.messages: list[InfrahubMessage] = []
        self.messages_per_routing_key: dict[str, list[InfrahubMessage]] = {}

    async def publish(
        self, message: InfrahubMessage, routing_key: str, delay: MessageTTL | None = None, is_retry: bool = False
    ) -> None:
        self.messages.append(message)
        if routing_key not in self.messages_per_routing_key:
            self.messages_per_routing_key[routing_key] = []
        self.messages_per_routing_key[routing_key].append(message)

    @property
    def seen_routing_keys(self) -> list[str]:
        return list(self.messages_per_routing_key.keys())

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        raise ValueError("BusRecorder.reply should not be called")

    async def rpc(
        self,
        message: InfrahubMessage,
        response_class: type[ResponseClass],
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> ResponseClass:
        raise ValueError("BusRecorder.rpc should not be called")


class BusSimulator(InfrahubMessageBus):
    def __init__(self) -> None:
        self.messages: list[InfrahubMessage] = []
        self.messages_per_routing_key: dict[str, list[InfrahubMessage]] = {}

        self.replies: dict[str, list[InfrahubMessage]] = defaultdict(list)
        build_component_registry()

    async def publish(
        self, message: InfrahubMessage, routing_key: str, delay: MessageTTL | None = None, is_retry: bool = False
    ) -> None:
        self.messages.append(message)
        if routing_key not in self.messages_per_routing_key:
            self.messages_per_routing_key[routing_key] = []
        self.messages_per_routing_key[routing_key].append(message)
        await execute_message(routing_key=routing_key, message_body=message.body, message_bus=self, skip_flow=True)

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        correlation_id = message.meta.correlation_id or "default"
        self.replies[correlation_id].append(message)

    async def rpc(
        self,
        message: InfrahubMessage,
        response_class: type[ResponseClass],
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> ResponseClass:
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


CALLBACK_QUEUE_NAME = "never-replying"


@dataclass(frozen=True)
class _NamedQueue:
    name: str


@dataclass(frozen=True)
class _NamedStream:
    config: _NamedQueue


class NeverReplyingBus(RabbitMQMessageBus):
    """Records every published message and never delivers a reply, so any rpc call times out.

    No connection is opened; only `rpc` and `send` are supported.
    """

    def __init__(self, rpc_timeout: int = 1) -> None:
        super().__init__(component_type=ComponentType.API_SERVER, settings=BrokerSettings(rpc_timeout=rpc_timeout))
        self.messages: list[InfrahubMessage] = []
        self.callback_queue = cast("AbstractQueue", _NamedQueue(name=CALLBACK_QUEUE_NAME))

    async def publish(
        self,
        message: InfrahubMessage,
        routing_key: str,
        delay: MessageTTL | None = None,
        is_retry: bool = False,
    ) -> None:
        self.messages.append(message)

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        raise ValueError("NeverReplyingBus.reply should not be called")


class UnreachableBrokerBus(NeverReplyingBus):
    """Fails every publish the way a broker that cannot be reached does."""

    async def publish(
        self,
        message: InfrahubMessage,
        routing_key: str,
        delay: MessageTTL | None = None,
        is_retry: bool = False,
    ) -> None:
        raise ConnectionResetError("broker went away")


class StalledPublishBus(NeverReplyingBus):
    """Never completes a publish, the way a broker withholding its confirmation does."""

    async def publish(
        self,
        message: InfrahubMessage,
        routing_key: str,
        delay: MessageTTL | None = None,
        is_retry: bool = False,
    ) -> None:
        await asyncio.Event().wait()


class NeverReplyingNATSBus(NATSMessageBus):
    """Records every published message and never delivers a reply, so any rpc call times out.

    No connection is opened; only `rpc` and `send` are supported.
    """

    def __init__(self, rpc_timeout: int = 1) -> None:
        super().__init__(component_type=ComponentType.API_SERVER, settings=BrokerSettings(rpc_timeout=rpc_timeout))
        self.messages: list[InfrahubMessage] = []
        self.callback_queue = cast("StreamInfo", _NamedStream(config=_NamedQueue(name=CALLBACK_QUEUE_NAME)))

    async def publish(
        self,
        message: InfrahubMessage,
        routing_key: str,
        delay: MessageTTL | None = None,
        is_retry: bool = False,
    ) -> None:
        self.messages.append(message)

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        raise ValueError("NeverReplyingNATSBus.reply should not be called")
