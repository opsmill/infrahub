from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

import httpx
from infrahub_sdk import Config, InfrahubClient

from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.registry import registry
from infrahub.git.repository import InfrahubRepository

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk.types import HTTPMethod
    from testcontainers.core.container import DockerContainer


@dataclass
class GogsServer:
    base_url: str
    port: str
    token: str
    admin: str
    password: str
    container: DockerContainer


def build_repository_client(
    *,
    repository_id: str,
    name: str,
    location: str,
    default_branch: str,
    internal_status: RepositoryInternalStatus = RepositoryInternalStatus.ACTIVE,
    schema_branches: tuple[str, ...] = ("main",),
) -> InfrahubClient:
    """Return a client that answers the one repository read a read-write construction performs.

    Every other request is answered as an empty success, matching what tests relied on before
    construction started reading the graph. Use this where the code under test builds the repository
    object itself, so the real resolution path runs. The schema comes from the live registry, so it
    cannot drift; the caller must have the core schema registered.
    """
    node = {
        "__typename": InfrahubKind.REPOSITORY,
        "id": repository_id,
        "name": {"value": name},
        "location": {"value": location},
        "default_branch": {"value": default_branch},
        "internal_status": {"value": internal_status.value},
    }

    async def requester(
        url: str,
        method: HTTPMethod,
        headers: dict[str, Any],
        timeout: int,
        payload: dict | None = None,
    ) -> httpx.Response:
        request = httpx.Request(method="POST", url="http://mock")
        if InfrahubKind.REPOSITORY in (payload or {}).get("query", ""):
            data = {InfrahubKind.REPOSITORY: {"count": 1, "edges": [{"node": node}]}}
            return httpx.Response(status_code=200, json={"data": data}, request=request)
        return httpx.Response(status_code=200, json={"data": {}}, request=request)

    client = InfrahubClient(config=Config(requester=requester))
    for branch in schema_branches:
        client.schema.set_cache(schema=registry.schema.get_sdk_schema_branch(name="main"), branch=branch)
    return client


async def clone_repository(
    *,
    id: str | UUID,
    name: str | Path,
    location: str | Path,
    client: InfrahubClient,
    default_branch: str = "main",
    internal_status: RepositoryInternalStatus = RepositoryInternalStatus.ACTIVE,
    infrahub_branch_name: str = "main",
    update_commit_value: bool = True,
) -> InfrahubRepository:
    """Clone a read-write repository with its graph-held configuration supplied directly.

    The production factory reads that configuration from the repository's node, which a test whose
    client cannot answer a node query has no way to serve. Tiers that do have a real client and a
    real node should call the factory instead, so the resolution path is exercised.
    """
    repo = InfrahubRepository(
        id=UUID(str(id)),
        name=str(name),
        location=str(location),
        client=client,
        default_branch=default_branch,
        internal_status=internal_status,
        infrahub_branch_name=infrahub_branch_name,
    )
    await repo.create_locally(
        checkout_ref=default_branch,
        infrahub_branch_name=infrahub_branch_name,
        update_commit_value=update_commit_value,
    )
    return repo


async def open_repository(
    *,
    id: str | UUID,
    name: str | Path,
    location: str | Path,
    client: InfrahubClient,
    default_branch: str = "main",
    internal_status: RepositoryInternalStatus = RepositoryInternalStatus.ACTIVE,
    infrahub_branch_name: str = "main",
    commit: str | None = None,
) -> InfrahubRepository:
    """Open an existing local copy of a read-write repository, re-cloning it if it is missing.

    The graph-free counterpart of the production factory, for the same reason as `clone_repository`.
    """
    repo = InfrahubRepository(
        id=UUID(str(id)),
        name=str(name),
        location=str(location),
        client=client,
        default_branch=default_branch,
        internal_status=internal_status,
        infrahub_branch_name=infrahub_branch_name,
    )
    await repo.initialize_local(commit=commit)
    return repo
