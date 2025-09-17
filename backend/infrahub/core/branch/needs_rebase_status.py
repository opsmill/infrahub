from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus


def raise_needs_rebase_error(branch_name: str) -> None:
    raise ValueError(f"Branch {branch_name} must be rebased before any updates can be made")


def check_need_rebase_status(branch: Branch) -> None:
    if branch.status == BranchStatus.NEED_REBASE:
        raise_needs_rebase_error(branch_name=branch.name)
