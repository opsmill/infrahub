from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from attr import Factory, dataclass

from infrahub.components import ComponentType
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.log import get_logger
from infrahub.message_bus.types import KVTTL
from infrahub.telemetry.resources import ProcessResources, WorkerResourceReading
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubCache
    from infrahub.services.adapters.message_bus import InfrahubMessageBus

PRIMARY_API_SERVER = "workers:primary:api_server"
WORKER_MATCH = re.compile(r":worker:([^:]+)")
RESOURCE_COMPONENT_MATCH = re.compile(r"workers:resources:([^:]+):worker:")

# The per-process resource read can transiently fail (a psutil hiccup, a momentary
# hostname-lookup failure); a few immediate retries cover that before the reading
# is written as null and the failure logged for traceability.
RESOURCE_READ_MAX_ATTEMPTS = 3

# Host stand-in written when the resource read fails outright; such a reading
# carries no figures and is dropped from the aggregate, so the value is never
# summed and only needs to be non-raising.
_UNKNOWN_HOST = "unknown"

log = get_logger()


@dataclass
class InfrahubComponent:
    cache: InfrahubCache
    db: InfrahubDatabase
    message_bus: InfrahubMessageBus
    component_type: ComponentType
    process_resources: ProcessResources = Factory(ProcessResources)

    @classmethod
    async def new(
        cls, cache: InfrahubCache, db: InfrahubDatabase, message_bus: InfrahubMessageBus, component_type: ComponentType
    ) -> InfrahubComponent:
        component = cls(cache=cache, db=db, message_bus=message_bus, component_type=component_type)
        await component.refresh_heartbeat()
        return component

    @property
    def component_names(self) -> list[str]:
        names = []
        if self.component_type == ComponentType.API_SERVER:
            names.append("api_server")
        elif self.component_type == ComponentType.GIT_AGENT:
            names.append("git_agent")
        return names

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
        for component in self.component_names:
            await self.cache.set(
                key=f"workers:active:{component}:worker:{WORKER_IDENTITY}",
                value=Timestamp().to_string(),
                expires=KVTTL.FIFTEEN,
            )
            await self.cache.set(
                key=f"workers:resources:{component}:worker:{WORKER_IDENTITY}",
                value=self._read_own_resources().model_dump_json(),
                expires=KVTTL.FIFTEEN,
            )
        if self.component_type == ComponentType.API_SERVER:
            await self._set_primary_api_server()
        await self.cache.set(
            key=f"workers:worker:{WORKER_IDENTITY}", value=Timestamp().to_string(), expires=KVTTL.TWO_HOURS
        )

    def _read_own_resources(self) -> WorkerResourceReading:
        """Read this process's resource allocation, retrying a transient failure.

        A read that still fails after its retries is logged with the component and
        the failing source, then reported as a null-valued reading so a worker that
        silently stops reporting resources leaves a trace rather than only an
        aggregate undercount.
        """
        last_error: Exception | None = None
        for _ in range(RESOURCE_READ_MAX_ATTEMPTS):
            try:
                return self.process_resources.read()
            except Exception as exc:
                last_error = exc

        log.warning(
            "Unable to read process resource allocation for telemetry; reporting null",
            component_type=self.component_type.name,
            worker_id=WORKER_IDENTITY,
            error=str(last_error),
        )
        return WorkerResourceReading(host=_UNKNOWN_HOST)

    async def read_worker_resources(self) -> dict[str, dict[str, WorkerResourceReading]]:
        """Return the latest worker resource readings grouped by component and host.

        Readings that fail to parse are skipped; the several processes of one host
        report identical values, so a later reading for a host simply overwrites
        the earlier one.
        """
        keys = await self.cache.list_keys(filter_pattern="workers:resources:*")
        values = await self.cache.get_values(keys=keys)

        grouped: dict[str, dict[str, WorkerResourceReading]] = {}
        for key, value in zip(keys, values, strict=False):
            if value is None:
                continue
            match = RESOURCE_COMPONENT_MATCH.search(key)
            if not match:
                continue
            try:
                reading = WorkerResourceReading.model_validate_json(value)
            except ValueError:
                continue
            grouped.setdefault(match.group(1), {})[reading.host] = reading
        return grouped

    async def _set_primary_api_server(self) -> None:
        result = await self.cache.set(
            key=PRIMARY_API_SERVER, value=WORKER_IDENTITY, expires=KVTTL.FIFTEEN, not_exists=True
        )
        if result:
            log.info("api_worker promoted to primary", worker_id=WORKER_IDENTITY)
        else:
            log.debug("Primary node already set")
            primary_id = await self.cache.get(key=PRIMARY_API_SERVER)
            if primary_id == WORKER_IDENTITY:
                log.debug("Primary node set but same as ours, refreshing lifetime")
                await self.cache.set(key=PRIMARY_API_SERVER, value=WORKER_IDENTITY, expires=KVTTL.FIFTEEN)


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
