from typing import Any

from fast_depends import Depends, inject
from infrahub_sdk.client import InfrahubClient
from infrahub_sdk.config import Config

from infrahub import config
from infrahub.components import ComponentType
from infrahub.database import InfrahubDatabase, get_db
from infrahub.services import InfrahubServices
from infrahub.services.adapters.cache import InfrahubCache
from infrahub.services.adapters.event import InfrahubEventService
from infrahub.services.adapters.http import InfrahubHTTP
from infrahub.services.adapters.http.httpx import HttpxAdapter
from infrahub.services.adapters.message_bus import InfrahubMessageBus
from infrahub.services.adapters.workflow import InfrahubWorkflow
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.services.adapters.workflow.worker import WorkflowWorkerExecution

_singletons: dict[str, Any] = {}


def build_client() -> InfrahubClient:
    if "client" not in _singletons:
        _singletons["client"] = InfrahubClient(
            config=Config(address=config.SETTINGS.main.internal_address, retry_on_failure=True)
        )
    return _singletons["client"]


@inject
def get_client(client: InfrahubClient = Depends(build_client)) -> InfrahubClient:  # noqa: B008
    return client


async def build_database() -> InfrahubDatabase:
    if "database" not in _singletons:
        _singletons["database"] = InfrahubDatabase(driver=await get_db(retry=1))
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
                component_type=ComponentType.GIT_AGENT, driver=config.SETTINGS.broker.driver
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


async def get_infrahub_services() -> InfrahubServices:
    if "services" not in _singletons:
        _singletons["services"] = await InfrahubServices.new(
            cache=await get_cache(),
            client=get_client(),
            database=await get_database(),
            message_bus=await get_message_bus(),
            workflow=get_workflow(),
            component_type=ComponentType.GIT_AGENT,
        )

    return _singletons["services"]
