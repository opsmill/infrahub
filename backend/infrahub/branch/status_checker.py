from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.branch.filters import BranchListFilters
from infrahub.core.merge.write_blocker import MergeProtectionState
from infrahub.exceptions import (
    BranchAlreadyMergedError,
    BranchNeedsRebaseError,
    MergeInProgressError,
    MergeRecoveryRequiredError,
)
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.core.merge.write_blocker import MergeProtection, MergeWriteBlocker
    from infrahub.database import InfrahubDatabase

log = get_logger()

MERGE_IN_PROGRESS_MESSAGE = "A merge is currently in progress; writes are temporarily blocked. Please retry shortly."

MERGE_RECOVERY_REQUIRED_MESSAGE = (
    "A previous merge failed and left the default branch protected. Writes stay blocked until an "
    "administrator runs `infrahub recover merge`. Please contact an administrator."
)


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
        """Check if writes are blocked by an in-progress or failed merge.

        Two branches are blocked: the merge *source* (it is heading to MERGED) and the *default*
        branch (the merge target). Its state decides the rejection:
          - MERGING: transient — the default branch becomes writable again once the merge completes,
            so the target gate raises the retryable MergeInProgressError, and
          - MERGE_FAILED: durable — a previous merge died, so the gate raises MergeRecoveryRequiredError
            (a distinct, non-retryable code) until an administrator runs ``infrahub recover merge``.

        If the cache lookup fails — unreachable backend, or a present-but-corrupt value that cannot be
        interpreted as "no merge in progress" — the gate falls back to the durable branch status in the
        database (the source of truth) rather than failing open. A cache outage therefore blocks writes
        only when a merge is genuinely in progress rather than freezing every default-branch write, and
        a corrupt value can never silently lift the block while a merge is still underway.

        Raises:
            MergeInProgressError: if the branch is blocked by an in-progress merge.
            MergeRecoveryRequiredError: if the branch is blocked by a failed merge awaiting recovery.

        """
        try:
            protection = await self.merge_write_blocker.get()
        except Exception:
            log.exception("merge-protection cache lookup failed; falling back to branch status in the database")
            await self._check_merging_status_from_db(branch)
            return

        if protection is None:
            return

        self._raise_if_blocked(branch=branch, protection=protection)

    def _raise_if_blocked(self, branch: Branch, protection: MergeProtection) -> None:
        is_source = branch.name == protection.branch
        if not (is_source or branch.is_default):
            return

        if protection.state == MergeProtectionState.MERGE_FAILED:
            raise MergeRecoveryRequiredError(
                identifier=branch.name,
                message=MERGE_RECOVERY_REQUIRED_MESSAGE,
                merging_branch=protection.branch,
            )

        message = _merging_branch_message(branch.name) if is_source else MERGE_IN_PROGRESS_MESSAGE
        raise MergeInProgressError(identifier=branch.name, message=message, merging_branch=protection.branch)

    async def _check_merging_status_from_db(self, branch: Branch) -> None:
        """Cache-unreachable fallback: enforce the gate from the durable branch status.

        Raises:
            MergeInProgressError: if the branch is blocked by an in-progress merge.
            MergeRecoveryRequiredError: if the branch is blocked by a failed merge awaiting recovery.

        """
        # Filter to protected branches server-side: an unfiltered list is capped at the default page
        # size, so on a deployment with many branches a merging/failed branch could be missed and the
        # block wrongly lifted. At most one branch is protected at a time.
        branches = await Branch.get_list(
            db=self.db,
            branch_filters=BranchListFilters(statuses=[BranchStatus.MERGE_FAILED, BranchStatus.MERGING]),
        )
        failed = sorted(b.name for b in branches if b.status == BranchStatus.MERGE_FAILED)
        merging = sorted(b.name for b in branches if b.status == BranchStatus.MERGING)

        # A durable MERGE_FAILED takes precedence: it needs recovery and is the more severe state.
        if failed and (branch.name in failed or branch.is_default):
            raise MergeRecoveryRequiredError(
                identifier=branch.name, message=MERGE_RECOVERY_REQUIRED_MESSAGE, merging_branch=failed[0]
            ) from None

        if branch.name in merging:
            raise MergeInProgressError(
                identifier=branch.name, message=_merging_branch_message(branch.name), merging_branch=branch.name
            ) from None

        if branch.is_default and merging:
            raise MergeInProgressError(
                identifier=branch.name, message=MERGE_IN_PROGRESS_MESSAGE, merging_branch=merging[0]
            ) from None

    async def check(self, branch: Branch) -> None:
        self.check_needs_rebase_status(branch)
        self.check_merge_status(branch)
        await self.check_merging_status(branch)
