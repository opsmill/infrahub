from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from infrahub.components import ComponentType
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import InitializationError
from infrahub.message_bus import messages
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices

PRIMARY_API_SERVER = "workers:primary:api_server"


class InfrahubComponent:
    def __init__(self) -> None:
        self._service: Optional[InfrahubServices] = None
        self.expires = 15

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

    async def list_component(self, component: str) -> list[str]:
        keys = await self.service.cache.list_keys(filter_pattern=f"workers:active:{component}:*")
        return [key.split(":")[-1] for key in keys]

    async def count_component(self, component: str) -> int:
        return len(await self.list_component(component=component))

    async def initialize(self, service: InfrahubServices) -> None:
        """Initialize the Message bus"""
        self._service = service

    async def is_primary_api(self) -> bool:
        primary_identity = await self.service.cache.get(PRIMARY_API_SERVER)
        return primary_identity == WORKER_IDENTITY

    async def _list_schema_hash(self, branch: str, component: str = "*") -> list[str]:
        keys = await self.service.cache.list_keys(filter_pattern=f"workers:schema_hash:branch:{branch}:{component}:*")
        return keys

    async def schema_hash_synced(self, branch: str, component: str = "*") -> bool:
        keys = await self._list_schema_hash(branch=branch, component=component)
        hashes = {key.split(":")[5] for key in keys}
        return len(hashes) == 1

    async def refresh_schema_hash(self, branches: Optional[list[str]] = None) -> None:
        branches = branches or list(registry.branch.keys())
        for branch in branches:
            schema_branch = registry.schema.get_schema_branch(name=branch)
            hash_value = schema_branch.get_hash()
            for component in self.component_names:
                await self.service.cache.set(
                    key=f"workers:schema_hash:branch:{branch}:{component}:{hash_value}:worker:{WORKER_IDENTITY}",
                    value=str(Timestamp()),
                    expires=self.expires,
                )

    async def refresh_heartbeat(self) -> None:
        for component in self.component_names:
            await self.service.cache.set(
                key=f"workers:active:{component}:{WORKER_IDENTITY}", value=str(Timestamp()), expires=self.expires
            )
        if self.service.component_type == ComponentType.API_SERVER:
            await self._set_primary_api_server()

        await self.refresh_schema_hash()

    async def _set_primary_api_server(self) -> None:
        result = await self.service.cache.set(
            key=PRIMARY_API_SERVER, value=WORKER_IDENTITY, expires=self.expires, not_exists=True
        )
        if result:
            await self.service.send(message=messages.EventWorkerNewPrimaryAPI(worker_id=WORKER_IDENTITY))
        else:
            self.service.log.debug("Primary node already set")
            primary_id = await self.service.cache.get(key=PRIMARY_API_SERVER)
            if primary_id == WORKER_IDENTITY:
                self.service.log.debug("Primary node set but same as ours, refreshing lifetime")
                await self.service.cache.set(key=PRIMARY_API_SERVER, value=WORKER_IDENTITY, expires=15)
