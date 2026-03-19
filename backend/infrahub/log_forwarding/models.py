from __future__ import annotations

from datetime import datetime  # noqa: TC003
from enum import IntEnum, StrEnum

from pydantic import BaseModel, computed_field

LOG_AUTH = 4
LOG_LOCAL0 = 16


class MessageType(StrEnum):
    AUDIT_EVENT = "audit_event"
    APPLICATION_LOG = "application_log"


class SyslogSeverity(IntEnum):
    """RFC 5424 severity codes."""

    EMERGENCY = 0
    ALERT = 1
    CRITICAL = 2
    ERROR = 3
    WARNING = 4
    NOTICE = 5
    INFORMATIONAL = 6
    DEBUG = 7


class SyslogMessage(BaseModel):
    message_type: MessageType
    timestamp: datetime
    payload: str  # JSON for audit events, text for app logs
    event_type: str | None = None  # e.g. "infrahub.node.created" (audit only)
    severity: int  # RFC 5424 severity code
    process_id: str  # worker identity

    @computed_field  # type: ignore[prop-decorator]
    @property
    def facility(self) -> int:
        """RFC 5424 facility: LOG_AUTH (4) for audit events, LOG_LOCAL0 (16) for app logs."""
        return {
            MessageType.AUDIT_EVENT: LOG_AUTH,
            MessageType.APPLICATION_LOG: LOG_LOCAL0,
        }.get(self.message_type, LOG_LOCAL0)
