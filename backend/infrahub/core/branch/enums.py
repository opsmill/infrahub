from infrahub.utils import InfrahubStringEnum


class BranchStatus(InfrahubStringEnum):
    OPEN = "OPEN"
    NEED_REBASE = "NEED_REBASE"
    NEED_UPGRADE_REBASE = "NEED_UPGRADE_REBASE"
    DELETING = "DELETING"
    MERGING = "MERGING"
    MERGED = "MERGED"


TERMINAL_BRANCH_STATUSES: tuple[BranchStatus, ...] = (BranchStatus.MERGED, BranchStatus.DELETING)
