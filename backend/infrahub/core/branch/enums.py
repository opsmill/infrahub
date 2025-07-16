from infrahub.utils import InfrahubStringEnum


class BranchStatus(InfrahubStringEnum):
    OPEN = "OPEN"
    NEED_REBASE = "NEED_REBASE"
    CLOSED = "CLOSED"
    DELETING = "DELETING"
