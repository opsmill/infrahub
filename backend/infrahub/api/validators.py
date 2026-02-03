from infrahub.core.branch import Branch
from infrahub.core.branch.merged_status import check_merged_status
from infrahub.core.branch.needs_rebase_status import check_need_rebase_status


class CheckBranchStatus:
    def __init__(self, branch: Branch) -> None:
        self.branch = branch

    def check(self) -> None:
        check_need_rebase_status(branch=self.branch)
        check_merged_status(branch=self.branch)
