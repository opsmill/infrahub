from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.exceptions import RepositoryConnectionError, RepositoryCredentialsError, RepositoryError
from infrahub.log import suppress_traceback_in_logs

from .import_errors import RepositoryImportError, log_import_failure
from .repository import FailedImport, ImportStep, InfrahubRepository, PendingObjectImport

if TYPE_CHECKING:
    from collections.abc import Mapping

    from infrahub_sdk.client import InfrahubClient

    from infrahub.lock import InfrahubLockRegistry

    from .divergence.models import ReconciledBranch
    from .integrator import ObjectImportPlan
    from .models import GitRepositoryAdd


@dataclass(frozen=True)
class SyncReport:
    """What a synchronization run did, for the caller to report on.

    ``skipped_branches`` are the remote branches left out because their name collides with Infrahub's
    default branch. ``imported_branches`` are the Infrahub branches whose import was applied, and
    ``failed_import_branches`` those whose import was attempted and failed. ``advanced_skipped_branches``
    are the skipped branches whose remote head moved during the run.
    """

    skipped_branches: tuple[str, ...]
    imported_branches: tuple[str, ...]
    failed_import_branches: tuple[str, ...]
    advanced_skipped_branches: tuple[str, ...]

    @property
    def attempted_import_branches(self) -> tuple[str, ...]:
        """The Infrahub branches the run tried to import, whether or not the import succeeded."""
        return self.imported_branches + self.failed_import_branches

    @property
    def reports_skipped_branches(self) -> bool:
        """Whether a synchronization cycle reports its skipped branches.

        It does when it skipped one and either imported a branch or saw a skipped branch receive a
        commit, so a cycle where nothing moved on the remote stays silent.
        """
        return bool(self.skipped_branches) and bool(self.imported_branches or self.advanced_skipped_branches)


@dataclass(frozen=True)
class SyncOutcome:
    """What a synchronization run did: its report, the branches it advanced and the branches that failed."""

    report: SyncReport
    reconciled: tuple[ReconciledBranch, ...]
    """The branches whose import succeeded, each with the commit it advanced to."""

    failed: tuple[FailedImport, ...]


@suppress_traceback_in_logs
class RepositoryBranchesFailedError(RepositoryError):
    """Raised when at least one branch failed to synchronize, carrying the outcome of the whole run.

    Registered so the logging layer drops the traceback Prefect writes when it leaves a flow: each
    branch failure was already logged once, and this error only summarizes them.
    """

    def __init__(self, identifier: str, outcome: SyncOutcome, message: str | None = None) -> None:
        super().__init__(identifier=identifier, message=message)
        self.outcome = outcome

    @property
    def report(self) -> SyncReport:
        return self.outcome.report


def raise_if_branches_failed(repo: InfrahubRepository, outcome: SyncOutcome) -> None:
    """Log every branch the run failed to synchronize and raise them as one error.

    Raises:
        RepositoryBranchesFailedError: When at least one branch failed to synchronize; the error
            carries the outcome of the whole run.

    """
    try:
        repo.raise_if_branches_failed(list(outcome.failed))
    except RepositoryError as exc:
        # Same identifier and message, so the original adds nothing to the chain.
        raise RepositoryBranchesFailedError(identifier=exc.identifier, outcome=outcome, message=exc.message) from None


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
    ) -> ObjectImportPlan:
        """Build the import of one branch.

        Raises:
            RepositoryImportError: When the import fails, with the branch already marked as failed.

        """

    @abstractmethod
    async def apply_branch_import(self, repo: InfrahubRepository, plan: ObjectImportPlan) -> None:
        """Apply a built import to the graph.

        Raises:
            RepositoryImportError: When the import fails, with the branch already marked as failed.

        """


async def import_branch(
    lock_registry: InfrahubLockRegistry,
    importer: RepositoryImporter,
    repo: InfrahubRepository,
    pending_import: PendingObjectImport,
) -> RepositoryImportError | None:
    """Import one branch, applying it under the repository lock, and return its failure instead of raising it.

    Any failure is returned, logged once, so a failed branch never stops the import of the other branches.

    Raises:
        RepositoryConnectionError: When the remote repository is unreachable.
        RepositoryCredentialsError: When the credentials for the remote repository are invalid.

    """
    try:
        plan = await importer.build_branch_import(repo, pending_import)
        async with lock_registry.get(name=repo.name, namespace="repository"):
            await importer.apply_branch_import(repo, plan)
    except (RepositoryConnectionError, RepositoryCredentialsError):
        raise
    except RepositoryImportError as exc:
        return exc
    except Exception as exc:  # noqa: BLE001
        # A failure the import did not convert is still recorded on its branch, so the other branches import.
        return log_import_failure(identifier=repo.name, branch_name=pending_import.infrahub_branch_name, exc=exc)
    return None


@dataclass(frozen=True)
class AddedRepository:
    """A repository that was cloned, and the failure of its default-branch import, if it failed."""

    repository: InfrahubRepository
    import_error: RepositoryImportError | None


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

    async def add(self, model: GitRepositoryAdd) -> AddedRepository:
        """Clone the repository and import its default branch.

        A failed default-branch import is returned rather than raised, so the caller can still
        synchronize the other branches.
        """
        async with self._lock_registry.get(name=model.repository_name, namespace="repository"):
            repo = await InfrahubRepository.new(
                id=model.repository_id,
                name=model.repository_name,
                location=model.location,
                client=self._client,
                infrahub_branch_name=model.infrahub_branch_name,
            )
            default_commit = repo.get_commit_value(branch_name=repo.default_branch, remote=False)
            repo.create_commit_worktree(commit=default_commit)

        pending_import = PendingObjectImport(
            infrahub_branch_name=model.infrahub_branch_name,
            git_branch_name=repo.default_branch,
            commit=default_commit,
        )
        import_error = await import_branch(
            lock_registry=self._lock_registry, importer=self._importer, repo=repo, pending_import=pending_import
        )
        return AddedRepository(repository=repo, import_error=import_error)


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

    async def sync(
        self,
        repo: InfrahubRepository,
        staging_branch: str | None = None,
        graph_commits: Mapping[str, str | None] | None = None,
    ) -> SyncOutcome:
        """Synchronize the repository and return what the run did, including the branches that failed.

        A branch that fails does not raise, so the caller can act on the branches that advanced first.

        Raises:
            RepositoryConnectionError: When the remote repository is unreachable.
            RepositoryCredentialsError: When the credentials for the remote repository are invalid.
            RepositoryError: When fetching the remote fails for another reason.
            CommitNotFoundError: When a commit the sync needs cannot be found.

        """
        async with self._lock_registry.get(name=repo.name, namespace="repository"):
            collected = await repo.collect_pending_imports(staging_branch=staging_branch, graph_commits=graph_commits)

        failed_imports = list(collected.failed_imports)
        reconciled: list[ReconciledBranch] = []
        imported_branches: list[str] = []
        failed_import_branches: list[str] = []
        for pending_import in collected.imports:
            import_error = await import_branch(
                lock_registry=self._lock_registry, importer=self._importer, repo=repo, pending_import=pending_import
            )
            if import_error is None:
                imported_branches.append(pending_import.infrahub_branch_name)
                if pending_import.reconciled is not None:
                    reconciled.append(pending_import.reconciled)
                continue
            failed_imports.append(
                FailedImport(
                    branch_name=pending_import.infrahub_branch_name, step=ImportStep.IMPORT, reason=import_error.message
                )
            )
            failed_import_branches.append(pending_import.infrahub_branch_name)

        report = SyncReport(
            skipped_branches=tuple(collected.skipped_branches),
            imported_branches=tuple(imported_branches),
            failed_import_branches=tuple(failed_import_branches),
            advanced_skipped_branches=tuple(collected.advanced_skipped_branches),
        )
        return SyncOutcome(report=report, reconciled=tuple(reconciled), failed=tuple(failed_imports))
