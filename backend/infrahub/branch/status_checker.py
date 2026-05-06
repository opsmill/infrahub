from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.exceptions import BranchAlreadyMergedError, BranchLockedForMergeError, BranchNeedsRebaseError

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class BranchStatusChecker:
    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def check(
        self,
        branch: Branch,
        check_merge: bool = True,
        check_needs_rebase: bool = True,
    ) -> None:
        """Run the branch-status gates against the authoritative DB state.

        A single database read covers every status flag we need so callers (such as the GraphQL
        middleware) that always check both rebase and merge state pay the cost of one query
        rather than one per check.
        """
        statuses_to_query: list[BranchStatus] = []
        if check_needs_rebase:
            statuses_to_query.append(BranchStatus.NEED_REBASE)
        if check_merge:
            statuses_to_query.extend([BranchStatus.MERGED, BranchStatus.MERGING])

        if not statuses_to_query:
            return

        branch_status_map = await Branch.get_branch_names_by_status(db=self.db, statuses=statuses_to_query)

        if check_needs_rebase:
            self._raise_if_needs_rebase(branch=branch, branch_status_map=branch_status_map)
        if check_merge:
            self._raise_if_merge_status(branch=branch, branch_status_map=branch_status_map)

    def _raise_if_needs_rebase(self, branch: Branch, branch_status_map: dict[BranchStatus, list[str]]) -> None:
        if branch.name in branch_status_map.get(BranchStatus.NEED_REBASE, []):
            raise BranchNeedsRebaseError(
                identifier=branch.name,
                message=f"Branch {branch.name} must be rebased before any updates can be made",
            )

    def _raise_if_merge_status(self, branch: Branch, branch_status_map: dict[BranchStatus, list[str]]) -> None:
        if branch.name in branch_status_map.get(BranchStatus.MERGED, []):
            raise BranchAlreadyMergedError(
                identifier=branch.name,
                message=f"Branch '{branch.name}' has been merged and is read-only. No modifications are allowed.",
            )

        merging_branches = branch_status_map.get(BranchStatus.MERGING, [])
        if branch.name in merging_branches:
            raise BranchAlreadyMergedError(
                identifier=branch.name,
                message=f"Branch '{branch.name}' is currently being merged and is read-only. No modifications are allowed.",
            )

        if branch.is_default and merging_branches:
            merging_branch_name = merging_branches[0]
            raise BranchLockedForMergeError(
                identifier=branch.name,
                message=(
                    f"Branch '{branch.name}' is locked because branch '{merging_branch_name}' is currently being merged."
                    " No modifications are allowed until the merge completes."
                ),
            )
