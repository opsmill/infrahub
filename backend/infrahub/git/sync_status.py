from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreGenericRepository
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class RepositoryBranchSyncStatusReader:
    """Reads the sync status a repository recorded on a branch itself.

    `sync_status` is branch-local, and an isolated branch that never imported a repository reads the value
    its base branch held when the branch was created. That inherited value says nothing about the branch, so
    it is not reported.
    """

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def get_status_written_on_branch(self, repository_id: str, branch: Branch) -> str | None:
        """Return the sync status written on `branch`, or None when the branch only inherits one.

        A value the branch wrote is at least as recent as `branched_from`: a rebase moves both the branch's
        own edges and `branched_from` to the rebase time, so the two are equal afterwards and the comparison
        must not be strict. An inherited value is frozen before `branched_from`.
        """
        repository = await NodeManager.get_one(
            db=self.db,
            id=repository_id,
            kind=CoreGenericRepository,
            branch=branch,
            include_metadata=MetadataOptions.UPDATED_AT,
        )
        if repository is None:
            return None

        updated_at = repository.sync_status._get_updated_at()
        if updated_at is None or updated_at < Timestamp(branch.get_branched_from()):
            return None
        return repository.sync_status.value
