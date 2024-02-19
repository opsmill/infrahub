import enum


class InfrahubClientMode(str, enum.Enum):
    DEFAULT = "default"
    TRACKING = "tracking"
    # IDEMPOTENT = "idempotent"
