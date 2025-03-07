from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable

from infrahub.components import ComponentType
from infrahub.exceptions import InitializationError
from infrahub.log import get_logger
from infrahub.message_bus.messages import ROUTING_KEY_MAP

from .adapters.event import InfrahubEventService
from .adapters.http.httpx import HttpxAdapter
from .adapters.workflow.local import WorkflowLocalExecution
from .adapters.workflow.worker import WorkflowWorkerExecution
from .component import InfrahubComponent
from .scheduler import InfrahubScheduler

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from infrahub.message_bus import InfrahubMessage
    from infrahub.message_bus.types import MessageTTL

    from .adapters.cache import InfrahubCache
    from .adapters.http import InfrahubHTTP
    from .adapters.message_bus import InfrahubMessageBus
    from .adapters.workflow import InfrahubWorkflow
    from .protocols import InfrahubLogger


class InfrahubServices:
    _cache: InfrahubCache | None
    _client: InfrahubClient | None
    _database: InfrahubDatabase | None
    _message_bus: InfrahubMessageBus | None
    _workflow: InfrahubWorkflow | None
    _component: InfrahubComponent | None

    log: InfrahubLogger
    component_type: ComponentType
    http: InfrahubHTTP
    event: InfrahubEventService
    scheduler: InfrahubScheduler

    def __init__(
        self,
        log: InfrahubLogger,
        component_type: ComponentType,
        http: InfrahubHTTP,
        event: InfrahubEventService,
        scheduler: InfrahubScheduler,
        cache: InfrahubCache | None = None,
        client: InfrahubClient | None = None,
        database: InfrahubDatabase | None = None,
        message_bus: InfrahubMessageBus | None = None,
        workflow: InfrahubWorkflow | None = None,
    ):
        """
        This method should not be called directly, use `new` instead for a proper initialization.
        """

        self._cache = cache
        self._client = client
        self._database = database
        self._message_bus = message_bus
        self._workflow = workflow
        self.log = log
        self.component_type = component_type
        self.http = http
        self.event = event
        self.scheduler = scheduler
        self._component = None

    @classmethod
    async def new(
        cls,
        cache: InfrahubCache | None = None,
        client: InfrahubClient | None = None,
        database: InfrahubDatabase | None = None,
        event: InfrahubEventService | None = None,
        message_bus: InfrahubMessageBus | None = None,
        workflow: InfrahubWorkflow | None = None,
        log: InfrahubLogger | None = None,
        component_type: ComponentType | None = None,
        http: InfrahubHTTP | None = None,
    ) -> InfrahubServices:
        """
        Instantiate InfrahubServices object, and finalize initializations of underlying services having a circular
        dependency with InfrahubServices.
        """

        component_type = component_type or ComponentType.NONE

        scheduler = InfrahubScheduler(component_type)
        service = cls(
            cache=cache,
            client=client,
            database=database,
            message_bus=message_bus,
            workflow=workflow,
            log=log or get_logger(),
            component_type=component_type,
            scheduler=scheduler,
            event=event or InfrahubEventService(message_bus),
            http=http or HttpxAdapter(),
        )

        # This circular dependency could be removed if InfrahubScheduler only depends on what it needs.
        scheduler.service = service

        if message_bus is not None:
            # Need circular dependency for injecting `service`  within `execute_message`. This might be removed
            # using proper dependency injections.
            message_bus.service = service

            if cache is not None and database is not None:
                component = await InfrahubComponent.new(
                    cache=cache, component_type=component_type, db=database, message_bus=message_bus
                )
                # We need to post init `service._component` because InfrahubComponent.new relies on message_bus
                # itself relying on service.
                service._component = component

        if workflow is not None:
            if isinstance(workflow, WorkflowWorkerExecution):
                assert service.component is not None
                # Ideally `WorkflowWorkerExecution.initialize` would be directly part of WorkflowWorkerExecution
                # constructor but this requires some redesign as it depends on InfrahubComponent which is instantiated
                # after workflow instantiation.
                await workflow.initialize(
                    component_is_primary_server=await service.component.is_primary_gunicorn_worker()
                )
            elif isinstance(workflow, WorkflowLocalExecution):
                # Circular dependency is only needed for injecting `service` within `execute_workflow` while testing.
                workflow.service = service

        return service

    @property
    def component(self) -> InfrahubComponent:
        if not self._component:
            raise InitializationError("Service is not initialized with a component")

        return self._component

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

    @property
    def database(self) -> InfrahubDatabase:
        if not self._database:
            raise InitializationError("Service is not initialized with a database")

        return self._database

    async def shutdown(self) -> None:
        await self.scheduler.shutdown()
        await self.message_bus.shutdown()

    async def send(self, message: InfrahubMessage, delay: MessageTTL | None = None, is_retry: bool = False) -> None:
        routing_key = ROUTING_KEY_MAP.get(type(message))
        if not routing_key:
            raise ValueError("Unable to determine routing key")
        await self.message_bus.publish(message, routing_key=routing_key, delay=delay, is_retry=is_retry)


ServiceFunction = Callable[[InfrahubServices], Awaitable[None]]
