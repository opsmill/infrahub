from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

import httpx
from git import Repo
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


@dataclass(frozen=True)
class LocalRemote:
    """A remote on disk whose default branch is ``trunk``, with a working copy to commit through."""

    directory: Path
    trunk: str
    repo: Repo

    @classmethod
    def create(cls, directory: Path, trunk: str, branches: list[str], head: str | None = None) -> LocalRemote:
        """Create the remote with an empty repository configuration, forking each branch from the trunk.

        The remote's HEAD, which a clone checks out as a local branch, is ``head`` when given and the
        trunk otherwise.
        """
        directory.mkdir()
        repo = Repo.init(directory, initial_branch=trunk)
        with repo.config_writer() as cfg:
            cfg.set_value("user", "name", "Test")
            cfg.set_value("user", "email", "test@test.local")
        (directory / ".infrahub.yml").write_text("---\n", encoding="utf-8")
        (directory / "data.txt").write_text("v1\n", encoding="utf-8")
        repo.index.add([".infrahub.yml", "data.txt"])
        repo.index.commit("First commit")
        for branch_name in branches:
            repo.git.branch(branch_name)
        if head is not None:
            repo.git.checkout(head)
        return cls(directory=directory, trunk=trunk, repo=repo)

    def create_branch(self, branch_name: str) -> None:
        self.repo.git.branch(branch_name, self.trunk)

    def commit(self, branch_name: str, files: dict[str, str]) -> str:
        """Commit the given files on a branch, creating it from the trunk when it does not exist yet."""
        remote_head = self.repo.active_branch.name
        if branch_name not in [head.name for head in self.repo.heads]:
            self.create_branch(branch_name)
        self.repo.git.checkout(branch_name)
        for name, content in files.items():
            (self.directory / name).write_text(content, encoding="utf-8")
        self.repo.index.add(list(files))
        commit = self.repo.index.commit(f"Update on {branch_name}").hexsha
        self.repo.git.checkout(remote_head)
        return commit

    def rewrite_branch(self, branch_name: str, files: dict[str, str]) -> str:
        """Replace the last commit of a branch with a new one, so the branch no longer holds the commit it replaced."""
        remote_head = self.repo.active_branch.name
        self.repo.git.checkout(branch_name)
        for name, content in files.items():
            (self.directory / name).write_text(content, encoding="utf-8")
        self.repo.index.add(list(files))
        self.repo.git.commit("--amend", "-m", f"Rewritten on {branch_name}")
        commit = self.repo.head.commit.hexsha
        self.repo.git.checkout(remote_head)
        return commit

    def move_branch(self, branch_name: str, commit: str) -> None:
        self.repo.git.branch("-f", branch_name, commit)

    def delete_branch(self, branch_name: str) -> None:
        self.repo.git.branch("-D", branch_name)


def build_repository_client(
    *,
    repository_id: str,
    name: str,
    location: str,
    default_branch: str,
    internal_status: RepositoryInternalStatus = RepositoryInternalStatus.ACTIVE,
    query_branches: tuple[str, ...] = ("main",),
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
        query = (payload or {}).get("query", "")
        # Only the construction read, which selects default_branch, returns a node; every other
        # query naming the repository kind gets an empty success.
        if InfrahubKind.REPOSITORY in query and "default_branch" in query:
            data = {InfrahubKind.REPOSITORY: {"count": 1, "edges": [{"node": node}]}}
            return httpx.Response(status_code=200, json={"data": data}, request=request)
        return httpx.Response(status_code=200, json={"data": {}}, request=request)

    client = InfrahubClient(config=Config(requester=requester))
    # An Infrahub branch inherits the default branch's schema, and no caller here diverges it, so the
    # one schema is cached under every branch this client will be asked to query. Caching per branch
    # from the registry would instead fail for a branch that exists only in the graph.
    schema = registry.schema.get_sdk_schema_branch(name=registry.default_branch)
    for branch in query_branches:
        client.schema.set_cache(schema=schema, branch=branch)
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
