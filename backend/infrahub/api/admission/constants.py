from enum import StrEnum


class RejectionReason(StrEnum):
    """Which mechanism shed a request. Doubles as the `reason` metric label."""

    STRESS = "stress"
    CODEL = "codel"
    BACKSTOP = "backstop"
