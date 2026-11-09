from infrahub.utils import InfrahubStringEnum


class BranchStatus(InfrahubStringEnum):
    OPEN = "OPEN"
    NEED_REBASE = "NEED_REBASE"
    NEED_UPGRADE_REBASE = "NEED_UPGRADE_REBASE"
    DELETING = "DELETING"
    MERGING = "MERGING"
    MERGE_FAILED = "MERGE_FAILED"
    MERGED = "MERGED"


TERMINAL_BRANCH_STATUSES: tuple[BranchStatus, ...] = (BranchStatus.MERGED, BranchStatus.DELETING)
