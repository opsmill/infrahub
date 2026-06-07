import asyncio
import threading
import weakref
from typing import Any

from fast_depends import Depends, inject
from infrahub_sdk.client import InfrahubClient
from infrahub_sdk.config import Config

from infrahub import config
from infrahub.components import ComponentType
from infrahub.constants.environment import INSTALLATION_TYPE
from infrahub.core.registry import registry
from infrahub.database import InfrahubDatabase, get_db
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

class _PerLoopSingletons:
    """A mapping that scopes cached singletons to the current event loop (FR-024).

    Loop-bound async clients (cache, message bus, component, http, ...) bind to
    the loop that builds them; under the embedded free-threaded backend each
    worker thread has its own loop, so they must not be shared across loops. This
    transparently routes the existing ``_singletons[...]`` access to a per-loop
    dict, so the ``build_*`` helpers need no changes. A process-global fallback
    dict is used when there is no running loop (e.g. sync CLI paths).
    """

    def __init__(self) -> None:
        self._by_loop: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict[str, Any]]" = (
            weakref.WeakKeyDictionary()
        )
        self._fallback: dict[str, Any] = {}
        self._lock = threading.Lock()

    def _store(self) -> dict[str, Any]:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return self._fallback
        with self._lock:
            store = self._by_loop.get(loop)
            if store is None:
                store = {}
                self._by_loop[loop] = store
            return store

    def __contains__(self, key: str) -> bool:
        return key in self._store()

    def __getitem__(self, key: str) -> Any:
        return self._store()[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._store()[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._store().get(key, default)

    def clear(self) -> None:
        with self._lock:
            self._by_loop.clear()
        self._fallback.clear()


_singletons = _PerLoopSingletons()

# Per-event-loop Neo4j databases (FR-024). The Neo4j async driver binds to the
# event loop that created it; under the embedded free-threaded backend each
# worker thread runs its own loop, so one shared driver cannot be awaited across
# loops ("got Future attached to a different loop"). Resolve an InfrahubDatabase
# per running loop instead of a single global singleton.
#
# Keyed on the loop OBJECT (not id(loop)) via WeakKeyDictionary: this avoids
# id-reuse aliasing when a loop is GC'd, and auto-drops a loop's entry if it dies
# without close_loop_database() being called. All access is guarded by a
# threading.Lock for free-threaded safety; the per-loop asyncio.Lock then
# serializes the (async) driver build within a single loop.
_db_by_loop: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, InfrahubDatabase]" = weakref.WeakKeyDictionary()
_db_loop_locks: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]" = weakref.WeakKeyDictionary()
_db_registry_lock = threading.Lock()

# Per-event-loop InfrahubServices (FR-024). Each embedded worker thread builds its
# own service on its loop; app.state.service is a proxy that routes to the current
# loop's service (see infrahub.server). Guarded by the shared registry lock.
_service_by_loop: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, Any]" = weakref.WeakKeyDictionary()


def clear_singletons() -> None:
    """Drop every cached singleton (and every per-loop database/service reference)."""
    _singletons.clear()
    with _db_registry_lock:
        _db_by_loop.clear()
        _db_loop_locks.clear()
        _service_by_loop.clear()


def _get_db_loop_lock(loop: asyncio.AbstractEventLoop) -> asyncio.Lock:
    # asyncio.Lock() (3.10+) binds to a loop on first use, not at construction, so
    # it is safe to create here under a threading.Lock and await it on its loop.
    with _db_registry_lock:
        lock = _db_loop_locks.get(loop)
        if lock is None:
            lock = asyncio.Lock()
            _db_loop_locks[loop] = lock
        return lock


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
    # singleton=False always builds a fresh, throwaway database (caller owns it).
    if not singleton:
        return InfrahubDatabase(driver=await get_db(retry=5))

    # Per running event loop (FR-024): one InfrahubDatabase per loop, built lazily.
    loop = asyncio.get_running_loop()
    with _db_registry_lock:
        db = _db_by_loop.get(loop)
    if db is not None:
        return db
    async with _get_db_loop_lock(loop):
        with _db_registry_lock:
            db = _db_by_loop.get(loop)
        if db is None:
            db = InfrahubDatabase(driver=await get_db(retry=5))
            with _db_registry_lock:
                _db_by_loop[loop] = db
        return db


async def close_loop_database() -> None:
    """Close the current running loop's database and drop it from the registry.

    Call at lifespan shutdown so each worker thread closes the driver it built on
    its own loop — closing it from another loop raises 'attached to a different
    loop' (FR-024).
    """
    loop = asyncio.get_running_loop()
    with _db_registry_lock:
        db = _db_by_loop.pop(loop, None)
        _db_loop_locks.pop(loop, None)
    if db is not None:
        await db.close()


def set_loop_service(service: Any) -> None:
    """Register the InfrahubServices built for the current event loop (FR-024)."""
    with _db_registry_lock:
        _service_by_loop[asyncio.get_running_loop()] = service


def get_loop_service() -> Any:
    """Return the InfrahubServices for the current event loop, or None."""
    with _db_registry_lock:
        return _service_by_loop.get(asyncio.get_running_loop())


async def close_loop_service() -> None:
    """Shut down and drop the current event loop's InfrahubServices (FR-024)."""
    with _db_registry_lock:
        service = _service_by_loop.pop(asyncio.get_running_loop(), None)
    if service is not None:
        await service.shutdown()


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
