from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable, Optional

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
    from .adapters.message_bus import InfrahubMessageBus
    from .adapters.workflow import InfrahubWorkflow
    from .protocols import InfrahubLogger


class InfrahubServices:
    _cache: Optional[InfrahubCache]
    _client: Optional[InfrahubClient]
    _database: Optional[InfrahubDatabase]
    _message_bus: Optional[InfrahubMessageBus]
    _workflow: Optional[InfrahubWorkflow]
    _component: Optional[InfrahubComponent]

    log: InfrahubLogger
    component_type: ComponentType
    http: HttpxAdapter
    event: InfrahubEventService
    scheduler: InfrahubScheduler

    def __init__(
        self,
        log: InfrahubLogger,
        component_type: ComponentType,
        http: HttpxAdapter,
        event: InfrahubEventService,
        scheduler: InfrahubScheduler,
        _cache: Optional[InfrahubCache] = None,
        _client: Optional[InfrahubClient] = None,
        _database: Optional[InfrahubDatabase] = None,
        _message_bus: Optional[InfrahubMessageBus] = None,
        _workflow: Optional[InfrahubWorkflow] = None,
        _component: Optional[InfrahubComponent] = None,
    ):
        """
        This method should not be called directly, use `new` instead for a proper initialization.
        """

        self._cache = _cache
        self._client = _client
        self._database = _database
        self._message_bus = _message_bus
        self._workflow = _workflow
        self._component = _component
        self.log = log
        self.component_type = component_type
        self.http = http
        self.event = event
        self.scheduler = scheduler

    @classmethod
    async def new(
        cls,
        cache: Optional[InfrahubCache] = None,
        client: Optional[InfrahubClient] = None,
        database: Optional[InfrahubDatabase] = None,
        message_bus: Optional[InfrahubMessageBus] = None,
        workflow: Optional[InfrahubWorkflow] = None,
        log: Optional[InfrahubLogger] = None,
        component_type: Optional[ComponentType] = None,
    ) -> InfrahubServices:
        """
        Instantiate InfrahubServices object, and finalize initializations of underlying services having a circular
        dependency with InfrahubServices.
        """

        component_type = component_type or ComponentType.NONE

        if cache is not None and database is not None and message_bus is not None:
            component: Optional[InfrahubComponent] = await InfrahubComponent.new(
                cache=cache, component_type=component_type, db=database, message_bus=message_bus
            )
        else:
            component = None

        scheduler = InfrahubScheduler(component_type)
        service = cls(
            _cache=cache,
            _client=client,
            _database=database,
            _message_bus=message_bus,
            _workflow=workflow,
            _component=component,
            log=log or get_logger(),
            component_type=component_type,
            scheduler=scheduler,
            event=InfrahubEventService(message_bus),
            http=HttpxAdapter(),
        )

        # This circular dependency could be removed if InfrahubScheduler only depends on what it needs.
        scheduler.service = service

        if message_bus is not None:
            # need circular dependency for injecting `service`  within `execute_message`
            message_bus.service = service

        if workflow is not None:
            if isinstance(workflow, WorkflowWorkerExecution):
                assert component is not None
                # Ideally `WorkflowWorkerExecution.initialize` would be directly part of WorkflowWorkerExecution
                # constructor but this requires some redesign as it depends on InfrahubComponent which is instantiated
                # after workflow instantiation.
                await workflow.initialize(component_is_primary_server=await component.is_primary_gunicorn_worker())
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

    async def send(self, message: InfrahubMessage, delay: Optional[MessageTTL] = None, is_retry: bool = False) -> None:
        routing_key = ROUTING_KEY_MAP.get(type(message))
        if not routing_key:
            raise ValueError("Unable to determine routing key")
        await self.message_bus.publish(message, routing_key=routing_key, delay=delay, is_retry=is_retry)


ServiceFunction = Callable[[InfrahubServices], Awaitable[None]]


# TODO Remove this code once services is no longer
class ServiceManager:
    # Optional because it is supposed to be really instantiated later
    _service: Optional[InfrahubServices] = None

    @property
    def service(self) -> InfrahubServices:
        if self._service is None:
            raise ValueError("ServiceManager.service is not initialized")
        return self._service

    @service.setter
    def service(self, _service: InfrahubServices) -> None:
        self._service = _service


services = ServiceManager()
