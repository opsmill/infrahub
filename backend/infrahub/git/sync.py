from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from infrahub.exceptions import RepositoryConnectionError, RepositoryCredentialsError

from .repository import FailedImport, ImportStep, InfrahubRepository, PendingObjectImport

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient

    from infrahub.lock import InfrahubLockRegistry

    from .integrator import ObjectImportPlan
    from .models import GitRepositoryAdd


class RepositoryImporter(ABC):
    """Imports the objects of a single synced branch into the graph.

    The import is split into a build phase, which reads the pinned commit worktree with no graph
    mutation other than recording that a sync is in progress, and an apply phase, which performs
    every other graph mutation. Callers run the apply phase under the repository lock so that
    concurrent imports of the same repository are serialized.
    """

    @abstractmethod
    async def build_branch_import(
        self, repo: InfrahubRepository, pending_import: PendingObjectImport
    ) -> ObjectImportPlan: ...

    @abstractmethod
    async def apply_branch_import(self, repo: InfrahubRepository, plan: ObjectImportPlan) -> None: ...


class RepositoryFileImporter(RepositoryImporter):
    """Imports a branch by reading the object files of its pinned commit worktree."""

    async def build_branch_import(
        self, repo: InfrahubRepository, pending_import: PendingObjectImport
    ) -> ObjectImportPlan:
        return await repo.build_import_plan(
            infrahub_branch_name=pending_import.infrahub_branch_name,
            git_branch_name=pending_import.git_branch_name,
            commit=pending_import.commit,
        )

    async def apply_branch_import(self, repo: InfrahubRepository, plan: ObjectImportPlan) -> None:
        await repo.apply_import_plan(plan)


class RepositoryAdder:
    """Adds a new repository, serializing the clone and the object import under the repository lock.

    The first locked phase covers the clone, the default-branch worktree creation, and writing the
    pinned commit back to the graph, which must stay consistent with each other. The default-branch
    object import is then built outside the lock, reading from the per-commit worktree pinned during
    the locked phase, and applied to the graph under the lock so that concurrent imports of the same
    repository are serialized.
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

        pending_import = PendingObjectImport(
            infrahub_branch_name=model.infrahub_branch_name,
            git_branch_name=repo.default_branch,
            commit=default_commit,
        )
        plan = await self._importer.build_branch_import(repo, pending_import)
        async with self._lock_registry.get(name=model.repository_name, namespace="repository"):
            await self._importer.apply_branch_import(repo, plan)
        return repo


class RepositorySyncer:
    """Synchronizes a repository, serializing the git mutations and each branch import under the lock.

    The lock serializes mutations of the repository's on-disk git state. Each synced branch is then
    built outside the lock, reading from the per-commit worktree pinned during the locked phase, and
    applied to the graph under the lock so that concurrent imports of the same repository are
    serialized.
    """

    def __init__(self, lock_registry: InfrahubLockRegistry, importer: RepositoryImporter) -> None:
        self._lock_registry = lock_registry
        self._importer = importer

    async def sync(self, repo: InfrahubRepository, staging_branch: str | None = None) -> None:
        async with self._lock_registry.get(name=repo.name, namespace="repository"):
            collected = await repo.collect_pending_imports(staging_branch=staging_branch)

        failed_imports = list(collected.failed_imports)
        for pending_import in collected.imports:
            try:
<<<<<<< HEAD
                await self._importer.import_branch(repo, pending_import)
=======
                plan = await self._importer.build_branch_import(repo, pending_import)
                async with self._lock_registry.get(name=repo.name, namespace="repository"):
                    await self._importer.apply_branch_import(repo, plan)
>>>>>>> origin/stable
            except (RepositoryConnectionError, RepositoryCredentialsError):
                raise
            except Exception as exc:
                # The import already records its own per-branch error status before re-raising, so
                # isolate the failure here to keep importing the remaining branches.
                failed_imports.append(
                    FailedImport(
                        branch_name=pending_import.infrahub_branch_name, step=ImportStep.IMPORT, reason=str(exc)
                    )
                )

        repo.raise_if_branches_failed(failed_imports)
