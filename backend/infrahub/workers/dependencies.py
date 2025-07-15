from typing import Any

from fast_depends import Depends, inject
from infrahub_sdk.client import InfrahubClient
from infrahub_sdk.config import Config

from infrahub import config
from infrahub.components import ComponentType
from infrahub.constants.environment import INSTALLATION_TYPE
from infrahub.database import InfrahubDatabase, get_db
from infrahub.services.adapters.cache import InfrahubCache
from infrahub.services.adapters.event import InfrahubEventService
from infrahub.services.adapters.http import InfrahubHTTP
from infrahub.services.adapters.http.httpx import HttpxAdapter
from infrahub.services.adapters.message_bus import InfrahubMessageBus
from infrahub.services.adapters.workflow import InfrahubWorkflow
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.services.adapters.workflow.worker import WorkflowWorkerExecution
from infrahub.services.component import InfrahubComponent

_singletons: dict[str, Any] = {}


def set_component_type(component_type: ComponentType) -> None:
    if "component_type" not in _singletons:
        _singletons["component_type"] = component_type


def get_component_type() -> ComponentType:
    try:
        return _singletons["component_type"]
    except KeyError as exc:
        raise ValueError("Component type is not set. It needs to be initialized before working with services.") from exc


def build_client() -> InfrahubClient:
    return InfrahubClient(config=Config(address=config.SETTINGS.main.internal_address, retry_on_failure=True))


@inject
def get_client(client: InfrahubClient = Depends(build_client)) -> InfrahubClient:  # noqa: B008
    return client


def build_installation_type() -> str:
    return INSTALLATION_TYPE


@inject
def get_installation_type(installation_type: str = Depends(build_installation_type)) -> str:
    return installation_type


async def build_database() -> InfrahubDatabase:
    if "database" not in _singletons:
        _singletons["database"] = InfrahubDatabase(driver=await get_db(retry=5))
    return _singletons["database"]


@inject
async def get_database(database: InfrahubDatabase = Depends(build_database)) -> InfrahubDatabase:  # noqa: B008
    return database


async def build_cache() -> InfrahubCache:
    if "cache" not in _singletons:
        _singletons["cache"] = config.OVERRIDE.cache or await InfrahubCache.new_from_driver(
            driver=config.SETTINGS.cache.driver
        )
    return _singletons["cache"]


@inject
async def get_cache(cache: InfrahubCache = Depends(build_cache)) -> InfrahubCache:  # noqa: B008
    return cache


async def build_message_bus() -> InfrahubMessageBus:
    if "message_bus" not in _singletons:
        _singletons["message_bus"] = config.OVERRIDE.message_bus or (
            await InfrahubMessageBus.new_from_driver(
                component_type=get_component_type(), driver=config.SETTINGS.broker.driver
            )
        )
    return _singletons["message_bus"]


@inject
async def get_message_bus(message_bus: InfrahubMessageBus = Depends(build_message_bus)) -> InfrahubMessageBus:  # noqa: B008
    return message_bus


async def build_event_service() -> InfrahubEventService:
    if "event_service" not in _singletons:
        _singletons["event_service"] = InfrahubEventService(message_bus=await get_message_bus())
    return _singletons["event_service"]


@inject
async def get_event_service(event_service: InfrahubEventService = Depends(build_event_service)) -> InfrahubEventService:  # noqa: B008
    return event_service


def build_workflow() -> InfrahubWorkflow:
    if "workflow" not in _singletons:
        _singletons["workflow"] = config.OVERRIDE.workflow or (
            WorkflowWorkerExecution()
            if config.SETTINGS.workflow.driver == config.WorkflowDriver.WORKER
            else WorkflowLocalExecution()
        )
    return _singletons["workflow"]


@inject
def get_workflow(workflow: InfrahubWorkflow = Depends(build_workflow)) -> InfrahubWorkflow:  # noqa: B008
    return workflow


def build_http_service() -> InfrahubHTTP:
    if "http_service" not in _singletons:
        _singletons["http_service"] = HttpxAdapter()
    return _singletons["http_service"]


@inject
def get_http(http_service: InfrahubHTTP = Depends(build_http_service)) -> InfrahubHTTP:  # noqa: B008
    return http_service


async def build_component() -> InfrahubComponent:
    if "component" not in _singletons:
        _singletons["component"] = await InfrahubComponent.new(
            cache=await get_cache(),
            component_type=get_component_type(),
            db=await get_database(),
            message_bus=await get_message_bus(),
        )
    return _singletons["component"]


@inject
async def get_component(component: InfrahubComponent = Depends(build_component)) -> InfrahubComponent:  # noqa: B008
    return component
