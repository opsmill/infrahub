from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from infrahub.git.repository import get_initialized_repo
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.git.repository import InfrahubReadOnlyRepository, InfrahubRepository
    from infrahub.lock import InfrahubLockRegistry
    from infrahub.message_bus.messages import RefreshGitFetch

log = get_logger()


class ConvergingRepository(Protocol):
    """The git operations a worker runs on its own clone to converge on another worker's commits."""

    async def fetch(self) -> bool: ...

    async def reset_to_commit(
        self,
        branch_name: str,
        commit: str,
        branch_id: str | None = None,
        create_if_missing: bool = False,
        update_commit_value: bool = True,
    ) -> None: ...

    async def pull(
        self,
        branch_name: str,
        branch_id: str | None = None,
        create_if_missing: bool = False,
        update_commit_value: bool = True,
    ) -> bool | str: ...


class ConvergingRepositoryLoader(Protocol):
    async def load(self, message: RefreshGitFetch) -> ConvergingRepository: ...


class InitializedRepositoryLoader:
    """Loads this worker's clone of the repository a fetch message names, cloning it when it is missing."""

    def __init__(self, client: InfrahubClient) -> None:
        self._client = client

    async def load(self, message: RefreshGitFetch) -> InfrahubReadOnlyRepository | InfrahubRepository:
        return await get_initialized_repo(
            client=self._client,
            repository_id=message.repository_id,
            name=message.repository_name,
            repository_kind=message.repository_kind,
            infrahub_branch_name=message.infrahub_branch_name,
        )


class WorktreeConverger:
    """Brings this worker's clone of a repository onto the commits another worker's fetch message pins."""

    def __init__(
        self, lock_registry: InfrahubLockRegistry, loader: ConvergingRepositoryLoader, worker_identity: str
    ) -> None:
        self._lock_registry = lock_registry
        self._loader = loader
        self._worker_identity = worker_identity

    async def converge(self, message: RefreshGitFetch) -> None:
        if message.meta and message.meta.initiator_id == self._worker_identity:
            log.info("Ignoring git fetch request originating from self", worker=self._worker_identity)
            return

        repo = await self._loader.load(message)

        # Hold the repo lock so the hard reset doesn't interleave with other git
        # operations on the same on-disk tree (merges, syncs, branch creation).
        async with self._lock_registry.get(name=message.repository_name, namespace="repository"):
            await repo.fetch()
            if message.commit:
                await repo.reset_to_commit(
                    branch_name=message.infrahub_branch_name,
                    commit=message.commit,
                    branch_id=message.infrahub_branch_id,
                    create_if_missing=True,
                    update_commit_value=False,
                )
            else:
                await repo.pull(
                    branch_name=message.infrahub_branch_name,
                    branch_id=message.infrahub_branch_id,
                    create_if_missing=True,
                    update_commit_value=False,
                )
