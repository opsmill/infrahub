from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Optional

from infrahub.components import ComponentType
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import InitializationError
from infrahub.message_bus import messages
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices

PRIMARY_API_SERVER = "workers:primary:api_server"
WORKER_MATCH = re.compile(r":worker:([^:]+)")


class InfrahubComponent:
    def __init__(self) -> None:
        self._service: Optional[InfrahubServices] = None

    @property
    def service(self) -> InfrahubServices:
        if not self._service:
            raise InitializationError("Component has not been initialized")

        return self._service

    @property
    def component_names(self) -> list[str]:
        names = []
        if self.service.component_type == ComponentType.API_SERVER:
            names.append("api_server")
        elif self.service.component_type == ComponentType.GIT_AGENT:
            names.append("git_agent")
        return names

    async def initialize(self, service: InfrahubServices) -> None:
        """Initialize the Message bus"""
        self._service = service

    async def is_primary_api(self) -> bool:
        primary_identity = await self.service.cache.get(PRIMARY_API_SERVER)
        return primary_identity == WORKER_IDENTITY

    async def list_workers(self, branch: str, schema_hash: bool) -> list[WorkerInfo]:
        keys = await self.service.cache.list_keys(filter_pattern="workers:*")

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
            response = await self.service.cache.get_values(keys=schema_hash_keys)

        for key, value in zip(schema_hash_keys, response):
            if match := WORKER_MATCH.search(key):
                identity = match.group(1)
                workers[identity].add_value(key=key, value=value)
        return list(workers.values())

    async def refresh_schema_hash(self, branches: Optional[list[str]] = None) -> None:
        branches = branches or list(registry.branch.keys())
        for branch in branches:
            schema_branch = registry.schema.get_schema_branch(name=branch)
            hash_value = schema_branch.get_hash()
            for component in self.component_names:
                await self.service.cache.set(
                    key=f"workers:schema_hash:branch:{branch}:{component}:worker:{WORKER_IDENTITY}",
                    value=hash_value,
                    expires=7200,
                )

    async def refresh_heartbeat(self) -> None:
        for component in self.component_names:
            await self.service.cache.set(
                key=f"workers:active:{component}:worker:{WORKER_IDENTITY}", value=str(Timestamp()), expires=15
            )
        if self.service.component_type == ComponentType.API_SERVER:
            await self._set_primary_api_server()
        await self.service.cache.set(key=f"workers:worker:{WORKER_IDENTITY}", value=str(Timestamp()), expires=7200)

    async def _set_primary_api_server(self) -> None:
        result = await self.service.cache.set(
            key=PRIMARY_API_SERVER, value=WORKER_IDENTITY, expires=15, not_exists=True
        )
        if result:
            await self.service.send(message=messages.EventWorkerNewPrimaryAPI(worker_id=WORKER_IDENTITY))
        else:
            self.service.log.debug("Primary node already set")
            primary_id = await self.service.cache.get(key=PRIMARY_API_SERVER)
            if primary_id == WORKER_IDENTITY:
                self.service.log.debug("Primary node set but same as ours, refreshing lifetime")
                await self.service.cache.set(key=PRIMARY_API_SERVER, value=WORKER_IDENTITY, expires=15)


class WorkerInfo:
    def __init__(self, identity: str) -> None:
        self.id = identity
        self.active = False
        self._schema_hash: Optional[str] = None

    @property
    def schema_hash(self) -> Optional[str]:
        """Return schema hash provided that the worker is active."""
        if self.active:
            return self._schema_hash

        return None

    def add_key(self, key: str) -> None:
        if "workers:active:" in key:
            self.active = True

    def add_value(self, key: str, value: Optional[str] = None) -> None:
        if ":schema_hash:" in key:
            self._schema_hash = value

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "active": self.active, "schema_hash": self.schema_hash}
