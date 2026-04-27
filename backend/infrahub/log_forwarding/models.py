from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime  # noqa: TC003
from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.auth import AccountSession, AuthType

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


class ExceptionLogType(StrEnum):
    PERMISSION_DENIED = "infrahub.permission.denied"


@dataclass(slots=True)
class ExceptionLogPayload:
    event: ExceptionLogType = field(metadata={"doc": "Event name for the specific exception type"})
    message: str = field(metadata={"doc": "Detailed message describing the exception"})
    branch: str = field(metadata={"doc": "Branch on which the operation was attempted"})


@dataclass(slots=True)
class PermissionDeniedPayload(ExceptionLogPayload):
    account_id: str = field(metadata={"doc": "ID of the account associated with the request"})
    auth_type: AuthType = field(metadata={"doc": "Authentication type used for the request"})
    ip_address: str = field(metadata={"doc": "IP address from which the request originated"})
    request_path: str = field(metadata={"doc": "API endpoint or path for the request"})
    operation: str | None = field(
        default=None, metadata={"doc": "Name of the operation being performed, GraphQL requests only"}
    )
    query_type: str | None = field(
        default=None, metadata={"doc": "Type of the query being executed: mutation or query, GraphQL requests only"}
    )
    graphql_operations: list[str] | None = field(
        default=None, metadata={"doc": "List of GraphQL operations requested, GraphQL requests only"}
    )
