from __future__ import annotations

import importlib
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, TypeVar

from infrahub.message_bus.messages import ROUTING_KEY_MAP

ResponseClass = TypeVar("ResponseClass")

if TYPE_CHECKING:
    from infrahub.components import ComponentType
    from infrahub.config import BrokerDriver, BrokerSettings
    from infrahub.message_bus import InfrahubMessage, InfrahubResponse
    from infrahub.message_bus.types import MessageTTL
    from infrahub.services import InfrahubServices


class InfrahubMessageBus(ABC):
    DELIVER_TIMEOUT: int = 30 * 60  # 30 minutes
    worker_bindings: list[str] = [
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
    event_bindings: list[str] = ["refresh.registry.*"]
    broadcasted_event_bindings: list[str] = ["refresh.git.*"]
    service: InfrahubServices

    async def shutdown(self) -> None:  # noqa: B027 We want a default empty behavior, so it's ok to have an empty non-abstract method.
        """Shutdown the Message bus"""

    @classmethod
    async def new(cls, component_type: ComponentType, settings: BrokerSettings | None = None) -> InfrahubMessageBus:
        raise NotImplementedError()

    @classmethod
    async def new_from_driver(
        cls, component_type: ComponentType, driver: BrokerDriver, settings: BrokerSettings | None = None
    ) -> InfrahubMessageBus:
        """Imports and initializes the correct class based on the supplied driver.

        This is to ensure that we only import the Python modules that we actually
        need to operate and not import all possible options.
        """
        module = importlib.import_module(driver.driver_module_path)
        broker_driver: InfrahubMessageBus = getattr(module, driver.driver_class_name)
        return await broker_driver.new(component_type=component_type, settings=settings)

    @abstractmethod
    async def publish(
        self, message: InfrahubMessage, routing_key: str, delay: MessageTTL | None = None, is_retry: bool = False
    ) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def rpc(self, message: InfrahubMessage, response_class: type[ResponseClass]) -> ResponseClass:
        raise NotImplementedError()

    async def send(self, message: InfrahubMessage, delay: MessageTTL | None = None, is_retry: bool = False) -> None:
        routing_key = ROUTING_KEY_MAP.get(type(message))
        if not routing_key:
            raise ValueError("Unable to determine routing key")
        await self.publish(message, routing_key=routing_key, delay=delay, is_retry=is_retry)

    # TODO rename it
    async def reply_if_initiator_meta(self, message: InfrahubResponse, initiator: InfrahubMessage) -> None:
        if initiator.meta:
            message.meta.correlation_id = initiator.meta.correlation_id
            routing_key = initiator.meta.reply_to or ""
            await self.reply(message, routing_key=routing_key)
