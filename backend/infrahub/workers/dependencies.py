from collections.abc import Awaitable, Callable
from typing import Any

from fast_depends import Depends, inject
from infrahub_sdk.client import InfrahubClient
from infrahub_sdk.config import Config

from infrahub import config
from infrahub.components import ComponentType
from infrahub.constants.environment import INSTALLATION_TYPE
from infrahub.core.registry import registry
from infrahub.database import InfrahubDatabase, get_db
from infrahub.health import probe_task_manager_db
from infrahub.ldap_auth.service import LDAPAuthService, LDAPAuthServiceCommunity
from infrahub.log_forwarding.service import LogForwardingService, LogForwardingServiceCommunity
from infrahub.services.adapters.cache import InfrahubCache
from infrahub.services.adapters.event import InfrahubEventService
from infrahub.services.adapters.http import InfrahubHTTP
from infrahub.services.adapters.http.httpx import HttpxAdapter
from infrahub.services.adapters.message_bus import InfrahubMessageBus
from infrahub.services.adapters.workflow import InfrahubWorkflow
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.services.adapters.workflow.worker import WorkflowWorkerExecution
from infrahub.services.component import InfrahubComponent
from infrahub.tls.registry import TlsContextRegistry

_singletons: dict[str, Any] = {}


def clear_singletons() -> None:
    """Drop every cached singleton."""
    _singletons.clear()


def set_component_type(component_type: ComponentType) -> None:
    if "component_type" not in _singletons:
        _singletons["component_type"] = component_type


def get_component_type() -> ComponentType:
    try:
        return _singletons["component_type"]
    except KeyError as exc:
        raise ValueError("Component type is not set. It needs to be initialized before working with services.") from exc


def build_client() -> InfrahubClient:
    client_config = Config(address=config.SETTINGS.main.internal_address, retry_on_failure=True)
    tls_regsistry = get_tls_registry()
    tls_ca_bundle = config.SETTINGS.http.tls_ca_bundle
    ssl_context = tls_regsistry.get(
        insecure=config.SETTINGS.http.tls_insecure, ca_bundle=tls_ca_bundle, force_verify=bool(tls_ca_bundle)
    )
    client_config.set_ssl_context(context=ssl_context)
    client = InfrahubClient(config=client_config)
    # Populate client schema cache using our internal schema cache
    if registry.schema:
        for branch in registry.schema.get_branches():
            client.schema.set_cache(schema=registry.schema.get_sdk_schema_branch(name=branch), branch=branch)

    return client


@inject
def get_client(client: InfrahubClient = Depends(build_client)) -> InfrahubClient:  # noqa: B008
    return client


def build_installation_type() -> str:
    return INSTALLATION_TYPE


@inject
def get_installation_type(installation_type: str = Depends(build_installation_type)) -> str:
    return installation_type


async def build_database(singleton: bool = True) -> InfrahubDatabase:
    if not singleton or "database" not in _singletons:
        db = InfrahubDatabase(driver=await get_db(retry=5))

        if singleton:
            _singletons["database"] = db

        return db

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
            WorkflowWorkerExecution(tls_registry=build_tls_registry())
            if config.SETTINGS.workflow.driver == config.WorkflowDriver.WORKER
            else WorkflowLocalExecution()
        )
    return _singletons["workflow"]


@inject
def get_workflow(workflow: InfrahubWorkflow = Depends(build_workflow)) -> InfrahubWorkflow:  # noqa: B008
    return workflow


def build_task_manager_db_probe() -> Callable[[], Awaitable[bool]]:
    return probe_task_manager_db


@inject
def get_task_manager_db_probe(
    probe: Callable[[], Awaitable[bool]] = Depends(build_task_manager_db_probe),  # noqa: B008
) -> Callable[[], Awaitable[bool]]:
    return probe


def build_tls_registry() -> TlsContextRegistry:
    if "tls_registry" not in _singletons:
        _singletons["tls_registry"] = TlsContextRegistry()
    return _singletons["tls_registry"]


@inject
def get_tls_registry(tls_registry: TlsContextRegistry = Depends(build_tls_registry)) -> TlsContextRegistry:  # noqa: B008
    return tls_registry


def build_http_service() -> InfrahubHTTP:
    if "http_service" not in _singletons:
        _singletons["http_service"] = HttpxAdapter(tls_registry=build_tls_registry())
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


def build_log_forwarding_service() -> LogForwardingService:
    if "log_forwarding_service" not in _singletons:
        _singletons["log_forwarding_service"] = LogForwardingServiceCommunity()
    return _singletons["log_forwarding_service"]


@inject
def get_log_forwarding_service(
    log_forwarding_service: LogForwardingService = Depends(build_log_forwarding_service),  # noqa: B008
) -> LogForwardingService:
    return log_forwarding_service


def build_ldap_auth_service() -> LDAPAuthService:
    if "ldap_auth_service" not in _singletons:
        _singletons["ldap_auth_service"] = LDAPAuthServiceCommunity()
    return _singletons["ldap_auth_service"]


@inject
def get_ldap_auth_service(
    ldap_auth_service: LDAPAuthService = Depends(build_ldap_auth_service),  # noqa: B008
) -> LDAPAuthService:
    return ldap_auth_service
