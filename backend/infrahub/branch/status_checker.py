from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.exceptions import BranchAlreadyMergedError, BranchNeedsRebaseError


class BranchStatusChecker:
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

    def check(self, branch: Branch) -> None:
        self.check_needs_rebase_status(branch)
        self.check_merge_status(branch)
