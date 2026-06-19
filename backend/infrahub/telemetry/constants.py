from enum import StrEnum

TELEMETRY_KIND: str = "community"
TELEMETRY_VERSION: str = "20260618"


class RemoteSendStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    SKIPPED = "skipped"
    FAILED = "failed"


DEFAULT_PAYLOAD_FORMAT: str = TELEMETRY_VERSION


class InfrahubType(StrEnum):
    COMMUNITY = "community"
    ENTERPRISE = "enterprise"
