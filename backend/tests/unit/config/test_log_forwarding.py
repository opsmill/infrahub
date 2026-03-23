import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from infrahub.config import (
    EnterpriseFeatures,
    ExtraLogLevel,
    LogForwardingDestination,
    LogForwardingDestinationType,
    LogForwardingSettings,
    SyslogFormat,
    SyslogProtocol,
    load,
)

TEST_DIR = Path(__file__).parent


def test_log_forwarding_destination_valid() -> None:
    dest = LogForwardingDestination(
        name="siem-primary", type=LogForwardingDestinationType.SYSLOG, host="syslog.example.com"
    )
    assert dest.name == "siem-primary"
    assert dest.type is LogForwardingDestinationType.SYSLOG
    assert dest.host == "syslog.example.com"
    assert dest.port is None
    assert dest.service_port == 514
    assert dest.protocol.value == "tcp"
    assert dest.format.value == "rfc5424"
    assert dest.tcp_framing.value == "newline"
    assert dest.tls_enabled is False
    assert dest.queue_size == 10000
    assert dest.max_reconnect_interval == 60
    assert dest.shutdown_drain_timeout == 10
    assert dest.forward_application_logs is False
    assert dest.min_log_severity == ExtraLogLevel.WARNING


@pytest.mark.parametrize("invalid_port", [0, -1, 65536, 70000])
def test_log_forwarding_destination_rejects_invalid_port(invalid_port: int) -> None:
    with pytest.raises(ValidationError):
        LogForwardingDestination(
            name="test", type=LogForwardingDestinationType.SYSLOG, host="localhost", port=invalid_port
        )


def test_log_forwarding_destination_rejects_tls_with_udp() -> None:
    with pytest.raises(ValueError, match="TLS is only supported with TCP protocol, not UDP"):
        LogForwardingDestination(
            name="test",
            type=LogForwardingDestinationType.SYSLOG,
            host="localhost",
            protocol=SyslogProtocol.UDP,
            tls_enabled=True,
        )


def test_log_forwarding_destination_allows_tls_with_tcp() -> None:
    dest = LogForwardingDestination(
        name="test",
        type=LogForwardingDestinationType.SYSLOG,
        host="localhost",
        port=6514,
        protocol=SyslogProtocol.TCP,
        tls_enabled=True,
    )
    assert dest.tls_enabled is True


@pytest.mark.parametrize(
    ("kwargs", "expected_port"),
    [
        ({}, 514),
        ({"protocol": SyslogProtocol.UDP}, 514),
        ({"tls_enabled": True}, 6514),
        ({"port": 1514}, 1514),
        ({"port": 1514, "tls_enabled": True}, 1514),
    ],
    ids=["tcp-default", "udp-default", "tls-default", "explicit-port", "explicit-overrides-tls"],
)
def test_service_port(kwargs: dict, expected_port: int) -> None:
    dest = LogForwardingDestination(name="test", host="localhost", **kwargs)
    assert dest.service_port == expected_port


@pytest.mark.parametrize("invalid_queue_size", [0, -5])
def test_log_forwarding_destination_rejects_invalid_queue_size(invalid_queue_size: int) -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        LogForwardingDestination(
            name="test",
            type=LogForwardingDestinationType.SYSLOG,
            host="localhost",
            port=514,
            queue_size=invalid_queue_size,
        )


def test_log_forwarding_settings_empty_destinations() -> None:
    settings = LogForwardingSettings()
    assert settings.destinations == []
    assert settings.enterprise_features == []


def test_log_forwarding_settings_duplicate_names_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicates found: dup"):
        LogForwardingSettings(
            destinations=[
                LogForwardingDestination(name="dup", type=LogForwardingDestinationType.SYSLOG, host="host1", port=514),
                LogForwardingDestination(name="dup", type=LogForwardingDestinationType.SYSLOG, host="host2", port=515),
            ]
        )


def test_log_forwarding_settings_multiple_duplicate_names_listed() -> None:
    with pytest.raises(ValidationError, match="duplicates found: aaa, bbb"):
        LogForwardingSettings(
            destinations=[
                LogForwardingDestination(name="aaa", type=LogForwardingDestinationType.SYSLOG, host="h1", port=514),
                LogForwardingDestination(name="bbb", type=LogForwardingDestinationType.SYSLOG, host="h2", port=514),
                LogForwardingDestination(name="aaa", type=LogForwardingDestinationType.SYSLOG, host="h3", port=514),
                LogForwardingDestination(name="bbb", type=LogForwardingDestinationType.SYSLOG, host="h4", port=514),
            ]
        )


def test_log_forwarding_settings_unique_names_accepted() -> None:
    settings = LogForwardingSettings(
        destinations=[
            LogForwardingDestination(name="primary", type=LogForwardingDestinationType.SYSLOG, host="host1", port=514),
            LogForwardingDestination(
                name="secondary", type=LogForwardingDestinationType.SYSLOG, host="host2", port=515
            ),
        ]
    )
    assert len(settings.destinations) == 2


def test_log_forwarding_enterprise_feature_not_detected_when_empty() -> None:
    config = load(config_data={})
    assert EnterpriseFeatures.LOG_FORWARDING not in config.enterprise_features


def test_log_forwarding_enterprise_feature_detected() -> None:
    settings = LogForwardingSettings(
        destinations=[
            LogForwardingDestination(
                name="siem", type=LogForwardingDestinationType.SYSLOG, host="syslog.example.com", port=514
            ),
        ]
    )
    assert EnterpriseFeatures.LOG_FORWARDING in settings.enterprise_features


def test_log_forwarding_toml_parsing_multiple_destinations() -> None:
    config_data = {
        "log_forwarding": {
            "destinations": [
                {
                    "name": "siem-primary",
                    "type": "syslog",
                    "host": "syslog.example.com",
                    "port": 514,
                    "protocol": "tcp",
                    "format": "rfc5424",
                },
                {
                    "name": "siem-secondary",
                    "type": "syslog",
                    "host": "syslog2.example.com",
                    "port": 1514,
                    "protocol": "udp",
                    "format": "rfc3164",
                },
            ]
        }
    }
    config = load(config_data=config_data)
    assert len(config.log_forwarding.destinations) == 2
    dest1 = config.log_forwarding.destinations[0]
    assert dest1.name == "siem-primary"
    assert dest1.host == "syslog.example.com"
    assert dest1.protocol is SyslogProtocol.TCP
    assert dest1.format is SyslogFormat.RFC5424
    dest2 = config.log_forwarding.destinations[1]
    assert dest2.name == "siem-secondary"
    assert dest2.host == "syslog2.example.com"
    assert dest2.protocol is SyslogProtocol.UDP
    assert dest2.format is SyslogFormat.RFC3164
    assert EnterpriseFeatures.LOG_FORWARDING in config.enterprise_features


def test_log_forwarding_destinations_from_environment_variable() -> None:
    destinations_json = json.dumps(
        [
            {"name": "siem1", "type": "syslog", "host": "host1.example.com", "port": 514},
            {"name": "siem2", "type": "syslog", "host": "host2.example.com", "port": 1514, "protocol": "udp"},
        ]
    )
    with patch.dict(os.environ, {"INFRAHUB_LOG_FORWARDING_DESTINATIONS": destinations_json}):
        settings = LogForwardingSettings()
    assert len(settings.destinations) == 2
    assert settings.destinations[0].name == "siem1"
    assert settings.destinations[0].host == "host1.example.com"
    assert settings.destinations[1].name == "siem2"
    assert settings.destinations[1].protocol.value == "udp"


def test_log_forwarding_from_toml_file() -> None:
    config_file = str(TEST_DIR / "log_forwarding_multi_dest.toml")
    config = load(config_file_name=config_file)

    assert len(config.log_forwarding.destinations) == 2
    assert EnterpriseFeatures.LOG_FORWARDING in config.enterprise_features

    primary = config.log_forwarding.destinations[0]
    assert primary.name == "siem-primary"
    assert primary.host == "syslog.example.com"
    assert primary.port == 514
    assert primary.protocol is SyslogProtocol.TCP
    assert primary.format is SyslogFormat.RFC5424
    assert primary.tls_enabled is True
    assert primary.tls_ca_bundle == "/etc/ssl/certs/ca-certificates.crt"
    assert primary.queue_size == 50000
    assert primary.forward_application_logs is True
    assert primary.min_log_severity == ExtraLogLevel.INFO

    backup = config.log_forwarding.destinations[1]
    assert backup.name == "backup-collector"
    assert backup.host == "syslog-backup.example.com"
    assert backup.port == 1514
    assert backup.protocol is SyslogProtocol.UDP
    assert backup.format is SyslogFormat.RFC3164
    assert backup.tls_enabled is False
    assert backup.queue_size == 5000
    assert backup.shutdown_drain_timeout == 5
    assert backup.forward_application_logs is False
    assert backup.min_log_severity == ExtraLogLevel.WARNING


def test_settings_enterprise_features_aggregates_log_forwarding() -> None:
    config_data = {
        "log_forwarding": {"destinations": [{"name": "siem", "type": "syslog", "host": "localhost", "port": 514}]},
        "policy": {"required_proposed_change_approvals": 2},
    }
    config = load(config_data=config_data)
    features = config.enterprise_features
    assert EnterpriseFeatures.LOG_FORWARDING in features
    assert EnterpriseFeatures.PROPOSED_CHANGE_REQUIRE_APPROVAL in features
