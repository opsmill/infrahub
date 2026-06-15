from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.branch.filters import BranchListFilters
from infrahub.exceptions import BranchAlreadyMergedError, BranchNeedsRebaseError
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.core.merge.write_blocker import MergeWriteBlocker
    from infrahub.database import InfrahubDatabase

log = get_logger()

MERGE_IN_PROGRESS_MESSAGE = "A merge is currently in progress; writes are temporarily blocked. Please retry shortly."


def _merging_branch_message(branch_name: str) -> str:
    return f"Branch '{branch_name}' is being merged and is read-only. No modifications are allowed."


class BranchStatusChecker:
    def __init__(self, db: InfrahubDatabase, merge_write_blocker: MergeWriteBlocker) -> None:
        self.db = db
        self.merge_write_blocker = merge_write_blocker

    def check_merge_status(self, branch: Branch) -> None:
        if branch.status == BranchStatus.MERGED:
            raise BranchAlreadyMergedError(
                identifier=branch.name,
                message=f"Branch '{branch.name}' has been merged and is read-only. No modifications are allowed.",
            )

    def check_needs_rebase_status(self, branch: Branch) -> None:
        if branch.status == BranchStatus.NEED_REBASE:
            raise BranchNeedsRebaseError(
                identifier=branch.name, message=f"Branch {branch.name} must be rebased before any updates can be made"
            )

    async def check_merging_status(self, branch: Branch) -> None:
        """Check if writes are blocked by an in-progress merge operation.

        The block is driven by the shared ``merge:protected`` cache key so every worker sees the same
        state with a single lookup:
          - source gate: the key's branch matches the branch being written — rejected with the same
            read-only message a merged branch gets (it is heading to MERGED), and
          - target gate: the branch being written is the default branch (the only merge target) —
            rejected with the transient message, since it becomes writable again after the merge.

        If the cache is unreachable, the exception is logged and the gate falls back to the durable
        branch status in the database (the source of truth), so a cache outage blocks writes only when
        a merge is genuinely in progress rather than freezing every default-branch write.

        Raises:
            BranchAlreadyMergedError: if the branch is blocked by a merge in progress.

        """
        try:
            protection = await self.merge_write_blocker.get()
        except Exception:
            log.exception("merge-protection cache unreachable; falling back to branch status in the database")
            await self._check_merging_status_from_db(branch)
            return

        if protection is None:
            return

        if branch.name == protection.branch:
            raise BranchAlreadyMergedError(identifier=branch.name, message=_merging_branch_message(branch.name))

        if branch.is_default:
            raise BranchAlreadyMergedError(identifier=branch.name, message=MERGE_IN_PROGRESS_MESSAGE)

    async def _check_merging_status_from_db(self, branch: Branch) -> None:
        """Cache-unreachable fallback: enforce the gate from the durable branch status.

        Raises:
            BranchAlreadyMergedError: if the branch is blocked by a merge in progress.

        """
        merging = await Branch.get_list(db=self.db, branch_filters=BranchListFilters(status=BranchStatus.MERGING))
        merging_branch_names = {merging_branch.name for merging_branch in merging}

        if branch.name in merging_branch_names:
            raise BranchAlreadyMergedError(
                identifier=branch.name, message=_merging_branch_message(branch.name)
            ) from None

        if branch.is_default and merging_branch_names:
            raise BranchAlreadyMergedError(identifier=branch.name, message=MERGE_IN_PROGRESS_MESSAGE) from None

    async def check(self, branch: Branch) -> None:
        self.check_needs_rebase_status(branch)
        self.check_merge_status(branch)
        await self.check_merging_status(branch)
