from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable, Optional

from infrahub.components import ComponentType
from infrahub.exceptions import InitializationError
from infrahub.log import get_logger
from infrahub.message_bus.messages import ROUTING_KEY_MAP

from .adapters.event import InfrahubEventService
from .adapters.http.httpx import HttpxAdapter
from .adapters.workflow.local import WorkflowLocalExecution
from .component import InfrahubComponent
from .scheduler import InfrahubScheduler

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from infrahub.message_bus import InfrahubMessage, InfrahubResponse
    from infrahub.message_bus.types import MessageTTL

    from .adapters.cache import InfrahubCache
    from .adapters.message_bus import InfrahubMessageBus
    from .adapters.workflow import InfrahubWorkflow
    from .protocols import InfrahubLogger


class InfrahubServices:
    def __init__(
        self,
        cache: Optional[InfrahubCache] = None,
        client: Optional[InfrahubClient] = None,
        database: Optional[InfrahubDatabase] = None,
        message_bus: Optional[InfrahubMessageBus] = None,
        workflow: Optional[InfrahubWorkflow] = None,
        event: InfrahubEventService | None = None,
        log: Optional[InfrahubLogger] = None,
        component_type: Optional[ComponentType] = None,
    ) -> None:
        self._cache = cache
        self._client = client
        self._database = database
        self._message_bus = message_bus
        self.event = event or InfrahubEventService()
        self.log = log or get_logger()
        self.component_type = component_type or ComponentType.NONE
        self.http = HttpxAdapter()
        self.scheduler = InfrahubScheduler()
        self.component = InfrahubComponent()
        self._workflow = workflow

        # Hack for testing purposes. WorkflowLocalExecution needs a reference to services within execute_workflow
        # and we don't want to call workflow.initialize within each of our tests.
        if isinstance(self._workflow, WorkflowLocalExecution):
            self._workflow.service = self

    @classmethod
    async def init_and_initialize(
        cls,
        cache: Optional[InfrahubCache] = None,
        client: Optional[InfrahubClient] = None,
        database: Optional[InfrahubDatabase] = None,
        message_bus: Optional[InfrahubMessageBus] = None,
        workflow: Optional[InfrahubWorkflow] = None,
        event: InfrahubEventService | None = None,
        log: Optional[InfrahubLogger] = None,
        component_type: Optional[ComponentType] = None,
    ) -> InfrahubServices:
        """
        Wrapper around `__init__` + `initialize`. We can't `initialize` within `__init__` because `__init__` can't be async.
        """

        service = cls(
            cache=cache,
            client=client,
            database=database,
            message_bus=message_bus,
            workflow=workflow,
            event=event,
            log=log,
            component_type=component_type,
        )
        await service.initialize()
        return service

    @property
    def message_bus(self) -> InfrahubMessageBus:
        if not self._message_bus:
            raise InitializationError("Service is not initialized with a message bus")

        return self._message_bus

    @property
    def workflow(self) -> InfrahubWorkflow:
        if not self._workflow:
            raise InitializationError("Service is not initialized with a workflow")

        return self._workflow

    @property
    def cache(self) -> InfrahubCache:
        if not self._cache:
            raise InitializationError("Service is not initialized with a cache")

        return self._cache

    @property
    def client(self) -> InfrahubClient:
        if not self._client:
            raise InitializationError("Service is not initialized with a client")

        return self._client

    def set_client(self, client: InfrahubClient | None) -> None:
        self._client = client

    @property
    def database(self) -> InfrahubDatabase:
        if not self._database:
            raise InitializationError("Service is not initialized with a database")

        return self._database

    async def initialize(self) -> None:
        # Each service has an extra reference to this InfrahubServices object for convenience.
        # Note that it could simplify code that each service has a reference to only what it needs. It would
        # at least avoid circular dependencies.

        if self._message_bus is not None:
            await self._message_bus.initialize(service=self)

        if self._cache is not None:
            await self._cache.initialize(service=self)

        await self.http.initialize(service=self)
        await self.component.initialize(service=self)
        await self.scheduler.initialize(service=self)

        if self._workflow is not None:
            await self._workflow.initialize(service=self)

        await self.event.initialize(service=self)

    async def shutdown(self) -> None:
        await self.scheduler.shutdown()
        await self.message_bus.shutdown()

    async def send(self, message: InfrahubMessage, delay: Optional[MessageTTL] = None, is_retry: bool = False) -> None:
        routing_key = ROUTING_KEY_MAP.get(type(message))
        if not routing_key:
            raise ValueError("Unable to determine routing key")
        await self.message_bus.publish(message, routing_key=routing_key, delay=delay, is_retry=is_retry)

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
