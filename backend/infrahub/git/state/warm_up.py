from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from git.exc import GitCommandError
from infrahub_sdk.protocols import CoreGenericRepository

from infrahub.core.constants import InfrahubKind
from infrahub.git.repository import get_initialized_repo
from infrahub.log import get_logger
from infrahub.message_bus import Meta, messages

from .log_reader import read_fetched_at

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.git.models import GitRepositoryWarmUp
    from infrahub.git.repository import InfrahubReadOnlyRepository, InfrahubRepository
    from infrahub.lock import InfrahubLock, InfrahubLockRegistry
    from infrahub.services.adapters.message_bus import InfrahubMessageBus

log = get_logger()


async def fetch_if_no_fetch_time(repo: InfrahubReadOnlyRepository | InfrahubRepository, lock: InfrahubLock) -> None:
    """Fetch a local copy that has no fetch time yet, so the reads report one.

    A failed fetch is logged rather than raised, and leaves the copy as the clone left it.
    """
    if not repo.has_origin:
        return
    git_repo = repo.get_git_repo_main()
    if read_fetched_at(repo=git_repo) is not None:
        return

    async with lock:
        # Another fetch may have run while this waited for the lock.
        if read_fetched_at(repo=git_repo) is not None:
            return
        try:
            await asyncio.to_thread(repo.fetch_from_origin, git_repo)
        except GitCommandError as exc:
            log.warning("Could not fetch the local copy", repository=repo.name, status=exc.status)


class RepositoryWarmUp:
    """Create a repository's local copy on the worker running this, then on every other worker."""

    def __init__(
        self,
        client: InfrahubClient,
        message_bus: InfrahubMessageBus,
        lock_registry: InfrahubLockRegistry,
        worker_identity: str,
    ) -> None:
        self._client = client
        self._message_bus = message_bus
        self._lock_registry = lock_registry
        self._worker_identity = worker_identity

    async def warm_up(self, model: GitRepositoryWarmUp) -> None:
        """Clone the repository here, ask every other worker to clone it too, then fetch the copy here.

        No local branch is moved, so the copies stay wherever their clone left them and a sync is
        never rolled back. A read-write repository with nothing imported on the branch is neither
        cloned nor broadcast; its sync creates the copy. The fetch only gives this copy a fetch time,
        so it runs after the broadcast and its failure is logged rather than raised.

        Raises:
            RepositoryError: When the repository cannot be cloned.

        """
        if model.repository_kind == InfrahubKind.REPOSITORY and not await self._has_imported_commit(model=model):
            log.info("Not warming up a repository with nothing imported", repository=model.repository_name)
            return

        # The clone takes the repository lock itself, and may be shared with a call already waiting for that lock.
        repo = await get_initialized_repo(
            client=self._client,
            repository_id=model.repository_id,
            name=model.repository_name,
            repository_kind=model.repository_kind,
            infrahub_branch_name=model.infrahub_branch_name,
        )
        await self._message_bus.send(
            message=messages.RefreshGitClone(
                meta=Meta(initiator_id=self._worker_identity),
                repository_id=model.repository_id,
                repository_name=model.repository_name,
                repository_kind=model.repository_kind,
                infrahub_branch_name=model.infrahub_branch_name,
            )
        )
        await fetch_if_no_fetch_time(
            repo=repo, lock=self._lock_registry.get(name=model.repository_name, namespace="repository")
        )

    async def _has_imported_commit(self, model: GitRepositoryWarmUp) -> bool:
        repository = await self._client.get(
            kind=CoreGenericRepository,
            id=model.repository_id,
            branch=model.infrahub_branch_name,
            include=["commit"],
        )
        return bool(repository.commit.value)
