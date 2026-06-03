from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.lock import InfrahubLockRegistry

    from .repository import BranchImport, InfrahubRepository


class RepositoryImporter(ABC):
    """Imports the objects of a single synced branch into the graph."""

    @abstractmethod
    async def import_branch(self, repo: InfrahubRepository, branch_import: BranchImport) -> None: ...


class RepositoryFileImporter(RepositoryImporter):
    """Imports a branch by reading the object files of its pinned commit worktree."""

    async def import_branch(self, repo: InfrahubRepository, branch_import: BranchImport) -> None:
        await repo.import_objects_from_files(  # type: ignore[call-overload]
            infrahub_branch_name=branch_import.infrahub_branch_name,
            git_branch_name=branch_import.git_branch_name,
            commit=branch_import.commit,
        )


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
        for branch_import in pending_imports:
            await self._importer.import_branch(repo, branch_import)
