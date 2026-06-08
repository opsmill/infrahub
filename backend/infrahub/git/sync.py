from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .repository import InfrahubRepository, PendingObjectImport

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient

    from infrahub.lock import InfrahubLockRegistry

    from .models import GitRepositoryAdd


class RepositoryImporter(ABC):
    """Imports the objects of a single synced branch into the graph."""

    @abstractmethod
    async def import_branch(self, repo: InfrahubRepository, pending_import: PendingObjectImport) -> None: ...


class RepositoryFileImporter(RepositoryImporter):
    """Imports a branch by reading the object files of its pinned commit worktree."""

    async def import_branch(self, repo: InfrahubRepository, pending_import: PendingObjectImport) -> None:
        await repo.import_objects_from_files(  # type: ignore[call-overload]
            infrahub_branch_name=pending_import.infrahub_branch_name,
            git_branch_name=pending_import.git_branch_name,
            commit=pending_import.commit,
        )


class RepositoryAdder:
    """Adds a new repository, holding the repository lock only for the git working-copy mutations.

    The lock serializes the clone and worktree creation. The default-branch object import runs after
    the lock is released; it reads from the per-commit worktree pinned during the locked phase, so it
    does not need the lock.
    """

    def __init__(
        self, lock_registry: InfrahubLockRegistry, importer: RepositoryImporter, client: InfrahubClient
    ) -> None:
        self._lock_registry = lock_registry
        self._importer = importer
        self._client = client

    async def add(self, model: GitRepositoryAdd) -> InfrahubRepository:
        async with self._lock_registry.get(name=model.repository_name, namespace="repository"):
            repo = await InfrahubRepository.new(
                id=model.repository_id,
                name=model.repository_name,
                location=model.location,
                client=self._client,
                infrahub_branch_name=model.infrahub_branch_name,
                internal_status=model.internal_status,
                default_branch_name=model.default_branch_name,
            )
            default_commit = repo.get_commit_value(branch_name=repo.default_branch, remote=False)
            repo.create_commit_worktree(commit=default_commit)

        await self._importer.import_branch(
            repo,
            PendingObjectImport(
                infrahub_branch_name=model.infrahub_branch_name,
                git_branch_name=repo.default_branch,
                commit=default_commit,
            ),
        )
        return repo


class RepositorySyncer:
    """Synchronizes a repository, holding the repository lock only for the git working-copy mutations.

    The lock serializes mutations of the repository's on-disk git state. The object import for each
    synced branch runs after the lock is released; it reads from the per-commit worktree pinned during
    the locked phase, so it does not need the lock.
    """

    def __init__(self, lock_registry: InfrahubLockRegistry, importer: RepositoryImporter) -> None:
        self._lock_registry = lock_registry
        self._importer = importer

    async def sync(self, repo: InfrahubRepository, staging_branch: str | None = None) -> None:
        async with self._lock_registry.get(name=repo.name, namespace="repository"):
            pending_imports = await repo.collect_pending_imports(staging_branch=staging_branch)
        for pending_import in pending_imports:
            await self._importer.import_branch(repo, pending_import)
