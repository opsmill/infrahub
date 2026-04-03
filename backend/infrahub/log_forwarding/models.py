from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime  # noqa: TC003
from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.auth import AccountSession

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


@dataclass(slots=True)
class SyslogMessage:
    message_type: MessageType
    timestamp: datetime
    payload: str  # JSON for audit events, text for app logs
    severity: int  # RFC 5424 severity code
    process_id: str  # worker identity
    event_type: str | None = None  # e.g. "infrahub.node.created" (audit only)

    @property
    def facility(self) -> int:
        """RFC 5424 facility: LOG_AUTH (4) for audit events, LOG_LOCAL0 (16) for app logs."""
        return {
            MessageType.AUDIT_EVENT: LOG_AUTH,
            MessageType.APPLICATION_LOG: LOG_LOCAL0,
        }.get(self.message_type, LOG_LOCAL0)


@dataclass(slots=True)
class LogForwardingContext:
    account_session: AccountSession | None
    branch_name: str
    ip_address: str
    request_path: str
    operation_name: str | None = None
    query_type: str | None = None
    graphql_operations: list[str] | None = None


@dataclass(slots=True)
class PermissionDeniedPayload:
    event: str
    message: str
    account_id: str
    auth_type: str
    branch: str
    ip_address: str
    request_path: str
    operation: str | None = None
    query_type: str | None = None
    graphql_operations: list[str] | None = None
