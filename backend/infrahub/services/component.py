from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from attr import dataclass

from infrahub.components import ComponentType
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.log import get_logger
from infrahub.message_bus.types import KVTTL
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubCache
    from infrahub.services.adapters.message_bus import InfrahubMessageBus

PRIMARY_API_SERVER = "workers:primary:api_server"
WORKER_MATCH = re.compile(r":worker:([^:]+)")

log = get_logger()


def get_component_names(component_type: ComponentType) -> list[str]:
    """Return the component labels a worker of this type reports under in the cache."""
    names = []
    if component_type == ComponentType.API_SERVER:
        names.append("api_server")
    elif component_type == ComponentType.GIT_AGENT:
        names.append("git_agent")
    return names


async def refresh_worker_heartbeat(cache: InfrahubCache, component_type: ComponentType) -> None:
    """Publish this worker's liveness to the cache.

    Writes the ``workers:active:*`` key whose 15-second expiry defines the active-worker set, keeps
    the primary API-server election alive, and refreshes the two-hour ``workers:worker:*`` presence
    key. The function only touches ``cache``, so it can run on any event loop as long as ``cache``
    was created on that loop; ``WorkerHeartbeat`` relies on this to beat from its own thread.

    Args:
        cache: Cache connection to write through.
        component_type: Type of the running process, which selects the keys to write.

    """
    for component in get_component_names(component_type):
        await cache.set(
            key=f"workers:active:{component}:worker:{WORKER_IDENTITY}",
            value=Timestamp().to_string(),
            expires=KVTTL.FIFTEEN,
        )
    if component_type == ComponentType.API_SERVER:
        await _set_primary_api_server(cache=cache)
    await cache.set(key=f"workers:worker:{WORKER_IDENTITY}", value=Timestamp().to_string(), expires=KVTTL.TWO_HOURS)


async def _set_primary_api_server(cache: InfrahubCache) -> None:
    result = await cache.set(key=PRIMARY_API_SERVER, value=WORKER_IDENTITY, expires=KVTTL.FIFTEEN, not_exists=True)
    if result:
        log.info("api_worker promoted to primary", worker_id=WORKER_IDENTITY)
    else:
        log.debug("Primary node already set")
        primary_id = await cache.get(key=PRIMARY_API_SERVER)
        if primary_id == WORKER_IDENTITY:
            log.debug("Primary node set but same as ours, refreshing lifetime")
            await cache.set(key=PRIMARY_API_SERVER, value=WORKER_IDENTITY, expires=KVTTL.FIFTEEN)


@dataclass
class InfrahubComponent:
    cache: InfrahubCache
    db: InfrahubDatabase
    message_bus: InfrahubMessageBus
    component_type: ComponentType

    @classmethod
    async def new(
        cls, cache: InfrahubCache, db: InfrahubDatabase, message_bus: InfrahubMessageBus, component_type: ComponentType
    ) -> InfrahubComponent:
        component = cls(cache=cache, db=db, message_bus=message_bus, component_type=component_type)
        await component.refresh_heartbeat()
        return component

    @property
    def component_names(self) -> list[str]:
        return get_component_names(self.component_type)

    async def is_primary_gunicorn_worker(self) -> bool:
        primary_identity = await self.cache.get(PRIMARY_API_SERVER)
        return primary_identity == WORKER_IDENTITY

    async def list_workers(self, branch: str, schema_hash: bool) -> list[WorkerInfo]:
        keys = await self.cache.list_keys(filter_pattern="workers:*")

        workers: dict[str, WorkerInfo] = {}
        for key in keys:
            if match := WORKER_MATCH.search(key):
                identity = match.group(1)
                if identity not in workers:
                    workers[identity] = WorkerInfo(identity=identity)
                workers[identity].add_key(key=key)

        response = []
        schema_hash_keys = []
        if schema_hash:
            schema_hash_keys = [key for key in keys if f":schema_hash:branch:{branch}" in key]
            response = await self.cache.get_values(keys=schema_hash_keys)

        for key, value in zip(schema_hash_keys, response, strict=False):
            if match := WORKER_MATCH.search(key):
                identity = match.group(1)
                workers[identity].add_value(key=key, value=value)
        return list(workers.values())

    async def list_active_worker_ids(self) -> set[str]:
        """Return the ids of the workers currently reporting an active heartbeat.

        Liveness is global: the active set is the same for every branch, so this takes no branch.
        """
        # ``branch`` only scopes the schema-hash lookup, which is skipped here, so its value is inert.
        workers = await self.list_workers(branch=registry.default_branch, schema_hash=False)
        return {worker.id for worker in workers if worker.active}

    async def refresh_schema_hash(self, branches: list[str] | None = None) -> None:
        branches = branches or list(registry.branch.keys())
        async with self.db.start_session(read_only=True) as safe_db:
            for branch in branches:
                if branch == GLOBAL_BRANCH_NAME:
                    continue
                schema_branch = registry.schema.get_schema_branch(name=branch)
                hash_value = schema_branch.get_hash()

                # Use branch name if we cannot find branch id in cache
                branch_id: str | None = None
                if branch_obj := await registry.get_branch(branch=branch, db=safe_db):
                    branch_id = str(branch_obj.uuid)

                if not branch_id:
                    branch_id = branch

                for component in self.component_names:
                    await self.cache.set(
                        key=f"workers:schema_hash:branch:{branch_id}:{component}:worker:{WORKER_IDENTITY}",
                        value=hash_value,
                        expires=KVTTL.TWO_HOURS,
                    )

    async def refresh_heartbeat(self) -> None:
        """Publish this worker's liveness once, through the main-loop cache connection.

        The recurring refresh runs on the ``WorkerHeartbeat`` thread; this is for the one-off writes
        at startup, before that thread exists.
        """
        await refresh_worker_heartbeat(cache=self.cache, component_type=self.component_type)


class WorkerInfo:
    def __init__(self, identity: str) -> None:
        self.id = identity
        self.active = False
        self._schema_hash: str | None = None

    @property
    def schema_hash(self) -> str | None:
        """Return schema hash provided that the worker is active."""
        if self.active:
            return self._schema_hash

        return None

    def add_key(self, key: str) -> None:
        if "workers:active:" in key:
            self.active = True

    def add_value(self, key: str, value: str | None = None) -> None:
        if ":schema_hash:" in key:
            self._schema_hash = value

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "active": self.active, "schema_hash": self.schema_hash}
