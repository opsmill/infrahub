from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus


def check_merged_status(branch: Branch) -> None:
    if branch.status == BranchStatus.MERGED:
        raise ValueError(f"Branch '{branch.name}' has been merged and is read-only. No modifications are allowed.")
