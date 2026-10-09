from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, assert_never

from infrahub.core.constants import MetadataOptions, RepositoryInternalStatus, RepositorySyncStatus
from infrahub.core.manager import NodeManager
from infrahub.core.order import OrderModel
from infrahub.core.protocols import CoreGenericRepository
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class BranchImportVerdict(StrEnum):
    """Whether the objects a repository registered on a branch match the content of that branch."""

    USABLE = "usable"
    FAILED = "failed"
    INCOMPLETE = "incomplete"


def classify_branch_import(
    sync_status: RepositorySyncStatus | None, internal_status: RepositoryInternalStatus
) -> BranchImportVerdict:
    """Classify a repository's import on a branch from the status the branch wrote itself.

    `sync_status` is None when the branch only inherits a status. A repository that is inactive on the branch is
    usable, so disabling it clears an earlier import failure.
    """
    if internal_status == RepositoryInternalStatus.INACTIVE or sync_status is None:
        return BranchImportVerdict.USABLE

    match sync_status:
        case RepositorySyncStatus.IN_SYNC:
            return BranchImportVerdict.USABLE
        case RepositorySyncStatus.ERROR_IMPORT:
            return BranchImportVerdict.FAILED
        case RepositorySyncStatus.SYNCING | RepositorySyncStatus.UNKNOWN:
            return BranchImportVerdict.INCOMPLETE
        case _:
            assert_never(sync_status)


@dataclass(frozen=True)
class RepositoryBranchSyncStatus:
    repository_name: str
    internal_status: RepositoryInternalStatus

    sync_status: RepositorySyncStatus | None
    """The status written on the branch itself, or None when the branch only inherits one."""

    @property
    def verdict(self) -> BranchImportVerdict:
        return classify_branch_import(sync_status=self.sync_status, internal_status=self.internal_status)


class RepositoryBranchSyncStatusReader:
    """Reads the sync status a repository recorded on a branch itself.

    `sync_status` is branch-local, and an isolated branch that never imported a repository reads the value
    its base branch held when the branch was created. That inherited value says nothing about the branch, so
    it is not reported.

    A value the branch wrote is at least as recent as `branched_from`: a rebase moves both the branch's own edges
    and `branched_from` to the rebase time, so the two are equal afterwards and the comparison must not be strict.
    An inherited value is frozen before `branched_from`. A value whose update time is unknown is reported, so a
    check fails closed rather than passing on missing metadata.
    """

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def get_status_written_on_branch(self, repository_id: str, branch: Branch) -> RepositorySyncStatus | None:
        """Return the sync status written on `branch`, or None when the branch only inherits one."""
        repository = await NodeManager.get_one(
            db=self.db,
            id=repository_id,
            kind=CoreGenericRepository,
            branch=branch,
            include_metadata=MetadataOptions.UPDATED_AT,
        )
        if repository is None:
            return None
        return self._get_written_status(repository=repository, branch=branch)

    async def list_statuses_on_branch(self, branch: Branch) -> list[RepositoryBranchSyncStatus]:
        """Return the status every repository visible on `branch` wrote on it."""
        repositories = await NodeManager.query(
            db=self.db,
            schema=CoreGenericRepository,
            branch=branch,
            fields={"name": None, "internal_status": None, "sync_status": None},
            include_metadata=MetadataOptions.UPDATED_AT,
            order=OrderModel(disable=True),
        )
        return [
            RepositoryBranchSyncStatus(
                repository_name=repository.name.value,
                internal_status=RepositoryInternalStatus(repository.internal_status.value),
                sync_status=self._get_written_status(repository=repository, branch=branch),
            )
            for repository in repositories
        ]

    def _get_written_status(self, repository: CoreGenericRepository, branch: Branch) -> RepositorySyncStatus | None:
        updated_at = repository.sync_status._get_updated_at()
        if updated_at is not None and updated_at < Timestamp(branch.get_branched_from()):
            return None
        return RepositorySyncStatus(repository.sync_status.value)
