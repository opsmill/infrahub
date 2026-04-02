from enum import StrEnum

TELEMETRY_KIND: str = "community"
TELEMETRY_VERSION: str = "20250318"

REMOTE_SEND_STATUS_PENDING: str = "pending"
REMOTE_SEND_STATUS_SENT: str = "sent"
REMOTE_SEND_STATUS_SKIPPED: str = "skipped"
REMOTE_SEND_STATUS_FAILED: str = "failed"

DEFAULT_PAYLOAD_FORMAT: str = TELEMETRY_VERSION


class InfrahubType(StrEnum):
    COMMUNITY = "community"
    ENTERPRISE = "enterprise"
