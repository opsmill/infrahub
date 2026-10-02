from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from infrahub_sdk.protocols import CoreGenericRepository

from infrahub.core.constants import InfrahubKind
from infrahub.git.repository import get_initialized_repo
from infrahub.log import get_logger
from infrahub.message_bus import Meta, messages

if TYPE_CHECKING:
    from git import Repo
    from infrahub_sdk import InfrahubClient

    from infrahub.git.models import GitRepositoryWarmUp
    from infrahub.lock import InfrahubLockRegistry
    from infrahub.services.adapters.message_bus import InfrahubMessageBus

log = get_logger()


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
        """Clone the repository here at the imported commit, then broadcast so every other worker holds a copy too.

        The imported commit is read with the repository lock held. Other workers receive a fetch
        pinned to it, or a clone-only request for a read-only branch with nothing imported. A
        read-write repository with nothing imported is neither cloned nor broadcast; its sync
        creates the copy.

        Raises:
            RepositoryError: When the repository cannot be cloned.
            GitCommandError: When the fetch from the remote fails.

        """
        async with self._lock_registry.get(name=model.repository_name, namespace="repository"):
            repository = await self._client.get(
                kind=CoreGenericRepository,
                id=model.repository_id,
                branch=model.infrahub_branch_name,
                include=["commit"],
            )
            imported_commit = repository.commit.value
            if not imported_commit and model.repository_kind == InfrahubKind.REPOSITORY:
                log.info("Not warming up a repository with nothing imported", repository=model.repository_name)
                return

            repo = await get_initialized_repo(
                client=self._client,
                repository_id=model.repository_id,
                name=model.repository_name,
                repository_kind=model.repository_kind,
                infrahub_branch_name=model.infrahub_branch_name,
            )
            await asyncio.to_thread(_fetch_forcing_tags, repo.get_git_repo_main())

            meta = Meta(initiator_id=self._worker_identity)
            if not imported_commit:
                await self._message_bus.send(
                    message=messages.RefreshGitClone(
                        meta=meta,
                        repository_id=model.repository_id,
                        repository_name=model.repository_name,
                        repository_kind=model.repository_kind,
                        infrahub_branch_name=model.infrahub_branch_name,
                    )
                )
                return

            branch = await self._client.branch.get(branch_name=model.infrahub_branch_name)
            await repo.reset_to_commit(
                branch_name=model.infrahub_branch_name,
                commit=imported_commit,
                branch_id=branch.id,
                create_if_missing=True,
                update_commit_value=False,
            )
            await self._message_bus.send(
                message=messages.RefreshGitFetch(
                    meta=meta,
                    location=model.location,
                    repository_id=model.repository_id,
                    repository_name=model.repository_name,
                    repository_kind=model.repository_kind,
                    infrahub_branch_name=model.infrahub_branch_name,
                    infrahub_branch_id=branch.id,
                    commit=imported_commit,
                )
            )


def _fetch_forcing_tags(git_repo: Repo) -> None:
    """Fetch from the remote, forcing tag updates, which git otherwise refuses for a tag moved upstream."""
    git_repo.remotes.origin.fetch(prune=True, tags=True, prune_tags=True, force=True)
