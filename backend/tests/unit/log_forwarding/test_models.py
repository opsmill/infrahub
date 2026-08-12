from dataclasses import asdict
from datetime import UTC, datetime

from infrahub.log_forwarding.models import LOG_AUTH, LOG_LOCAL0, MessageType, SyslogMessage, SyslogSeverity


def test_syslog_message_audit_event() -> None:
    msg = SyslogMessage(
        message_type=MessageType.AUDIT_EVENT,
        timestamp=datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC),
        payload='{"action": "node.created", "user": "admin"}',
        event_type="infrahub.node.created",
        severity=6,
        process_id="worker-1",
    )
    assert msg.message_type == MessageType.AUDIT_EVENT
    assert msg.event_type == "infrahub.node.created"
    assert msg.facility == LOG_AUTH
    assert msg.severity == SyslogSeverity.INFORMATIONAL


def test_syslog_message_application_log() -> None:
    msg = SyslogMessage(
        message_type=MessageType.APPLICATION_LOG,
        timestamp=datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC),
        payload="Connection timeout",
        event_type=None,
        severity=4,
        process_id="worker-2",
    )
    assert msg.message_type == MessageType.APPLICATION_LOG
    assert msg.event_type is None
    assert msg.facility == LOG_LOCAL0
    assert msg.severity == 4  # Warning


def test_syslog_message_event_type_defaults_to_none() -> None:
    msg = SyslogMessage(
        message_type=MessageType.APPLICATION_LOG,
        timestamp=datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC),
        payload="test",
        severity=7,
        process_id="worker-1",
    )
    assert msg.event_type is None


def test_syslog_message_serialization_roundtrip() -> None:
    msg = SyslogMessage(
        message_type=MessageType.AUDIT_EVENT,
        timestamp=datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC),
        payload='{"key": "value"}',
        event_type="infrahub.node.updated",
        severity=6,
        process_id="worker-1",
    )
    data = asdict(msg)
    restored = SyslogMessage(**data)
    assert restored == msg
