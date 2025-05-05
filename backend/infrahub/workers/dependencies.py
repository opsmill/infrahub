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

client: InfrahubClient | None = None
database: InfrahubDatabase | None = None
cache: InfrahubCache | None = None
message_bus: InfrahubMessageBus | None = None
event_service: InfrahubEventService | None = None
workflow: InfrahubWorkflow | None = None
http: InfrahubHTTP | None = None
services: InfrahubServices | None = None


def build_client() -> InfrahubClient:
    global client
    if client is None:
        client = InfrahubClient(config=Config(address=config.SETTINGS.main.internal_address, retry_on_failure=True))
    return client


@inject
def get_client(client: InfrahubClient = Depends(build_client)) -> InfrahubClient:  # noqa: B008
    return client


async def build_database() -> InfrahubDatabase:
    global database
    if database is None:
        database = InfrahubDatabase(driver=await get_db(retry=1))
    return database


@inject
async def get_database(database: InfrahubDatabase = Depends(build_database)) -> InfrahubDatabase:  # noqa: B008
    return database


async def build_cache() -> InfrahubCache:
    global cache
    if cache is None:
        cache = config.OVERRIDE.cache or (await InfrahubCache.new_from_driver(driver=config.SETTINGS.cache.driver))
    return cache


@inject
async def get_cache(cache: InfrahubCache = Depends(build_cache)) -> InfrahubCache:  # noqa: B008
    return cache


async def build_message_bus() -> InfrahubMessageBus:
    global message_bus
    if message_bus is None:
        message_bus = config.OVERRIDE.message_bus or (
            await InfrahubMessageBus.new_from_driver(
                component_type=ComponentType.GIT_AGENT, driver=config.SETTINGS.broker.driver
            )
        )
    return message_bus


@inject
async def get_message_bus(message_bus: InfrahubMessageBus = Depends(build_message_bus)) -> InfrahubMessageBus:  # noqa: B008
    return message_bus


@inject
async def build_event_service() -> InfrahubEventService:
    global event_service
    if event_service is None:
        event_service = InfrahubEventService(message_bus=await get_message_bus())
    return event_service


@inject
async def get_event_service(event_service: InfrahubEventService = Depends(build_event_service)) -> InfrahubEventService:  # noqa: B008
    return event_service


def build_workflow() -> InfrahubWorkflow:
    global workflow
    if workflow is None:
        workflow = config.OVERRIDE.workflow or (
            WorkflowWorkerExecution()
            if config.SETTINGS.workflow.driver == config.WorkflowDriver.WORKER
            else WorkflowLocalExecution()
        )
    return workflow


@inject
def get_workflow(workflow: InfrahubWorkflow = Depends(build_workflow)) -> InfrahubWorkflow:  # noqa: B008
    return workflow


def build_http() -> InfrahubHTTP:
    global http
    if http is None:
        http = HttpxAdapter()
    return http


@inject
def get_http(http: InfrahubHTTP = Depends(build_http)) -> InfrahubHTTP:  # noqa: B008
    return http


async def get_infrahub_services() -> InfrahubServices:
    # We have some form a circular dependency between:
    # 1. InfrahubServuces and InfrahubMessageBus
    # 2. InfrahubServices and InfrahubWorkflow
    global services
    if services is None:
        services = await InfrahubServices.new(
            cache=await get_cache(),
            client=get_client(),
            database=await get_database(),
            message_bus=await get_message_bus(),
            workflow=get_workflow(),
            component_type=ComponentType.GIT_AGENT,
        )

    return services
