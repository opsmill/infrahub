from typing import Awaitable, Callable, Optional

from infrahub_sdk import InfrahubClient

from infrahub.components import ComponentType
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import InitializationError
from infrahub.log import get_logger
from infrahub.message_bus import InfrahubMessage, InfrahubResponse
from infrahub.message_bus.messages import ROUTING_KEY_MAP
from infrahub.message_bus.types import MessageTTL

from .adapters.cache import InfrahubCache
from .adapters.message_bus import InfrahubMessageBus
from .protocols import InfrahubLogger
from .scheduler import InfrahubScheduler


class InfrahubServices:
    def __init__(
        self,
        cache: Optional[InfrahubCache] = None,
        client: Optional[InfrahubClient] = None,
        database: Optional[InfrahubDatabase] = None,
        message_bus: Optional[InfrahubMessageBus] = None,
        log: Optional[InfrahubLogger] = None,
        component_type: Optional[ComponentType] = None,
    ):
        self.cache = cache or InfrahubCache()
        self._client = client
        self._database = database
        self.message_bus = message_bus or InfrahubMessageBus()
        self.log = log or get_logger()
        self.component_type = component_type or ComponentType.NONE
        self.scheduler = InfrahubScheduler()

    @property
    def client(self) -> InfrahubClient:
        if not self._client:
            raise InitializationError()

        return self._client

    @property
    def database(self) -> InfrahubDatabase:
        if not self._database:
            raise InitializationError("Service is not initialized with a database")

        return self._database

    async def initialize(self) -> None:
        """Initialize the Services"""
        await self.message_bus.initialize(service=self)
        await self.scheduler.initialize(service=self)

    async def send(self, message: InfrahubMessage, delay: Optional[MessageTTL] = None) -> None:
        routing_key = ROUTING_KEY_MAP.get(type(message))
        if not routing_key:
            raise ValueError("Unable to determine routing key")
        await self.message_bus.publish(message, routing_key=routing_key, delay=delay)

    async def reply(self, message: InfrahubResponse, initiator: InfrahubMessage) -> None:
        if initiator.meta:
            message.meta.correlation_id = initiator.meta.correlation_id
            routing_key = initiator.meta.reply_to or ""
            await self.message_bus.reply(message, routing_key=routing_key)


class ServiceManager:
    def __init__(self) -> None:
        self.service = InfrahubServices()
        self.send = self.service.send

    def prepare(self, service: InfrahubServices) -> None:
        self.service = service
        self.send = self.service.send


ServiceFunction = Callable[[InfrahubServices], Awaitable[None]]


services = ServiceManager()
