from enum import StrEnum

TELEMETRY_KIND: str = "community"
TELEMETRY_VERSION: str = "20260628"


class RemoteSendStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    SKIPPED = "skipped"
    FAILED = "failed"


DEFAULT_PAYLOAD_FORMAT: str = TELEMETRY_VERSION


class InfrahubType(StrEnum):
    COMMUNITY = "community"
    ENTERPRISE = "enterprise"


class WorkflowRunState(StrEnum):
    """The end states of a workflow run that the report counts; the values are also the ``state`` of a run row."""

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CRASHED = "CRASHED"
    CANCELLED = "CANCELLED"
