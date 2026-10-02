from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.query.node import NodeListGetAttributeQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

SYNC_STATUS_ATTRIBUTE = "sync_status"


class RepositoryBranchSyncStatusReader:
    """Reads the sync status a repository recorded on a branch itself.

    `sync_status` is branch-local, and an isolated branch that never imported a repository reads the value
    its base branch held when the branch was created. That inherited value says nothing about the branch, so
    it is not reported.
    """

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def get_status_written_on_branch(self, repository_id: str, branch: Branch) -> str | None:
        """Return the sync status written on `branch`, or None when the branch only inherits one."""
        query = await NodeListGetAttributeQuery.init(
            db=self.db, ids=[repository_id], fields={SYNC_STATUS_ATTRIBUTE: True}, branch=branch
        )
        await query.execute(db=self.db)
        try:
            attribute, result = query.get_result_by_id_and_name(repository_id, SYNC_STATUS_ATTRIBUTE)
        except IndexError:
            return None

        if result.get("r2").get("branch") != branch.name:
            return None
        return attribute.value
