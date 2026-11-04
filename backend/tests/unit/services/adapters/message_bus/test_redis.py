from __future__ import annotations

import ssl
from dataclasses import dataclass
from pathlib import Path

import pytest
from redis.asyncio.connection import SSLConnection

from infrahub.components import ComponentType
from infrahub.config import BrokerDriver, BrokerSettings
from infrahub.services.adapters.message_bus.redis import RedisMessageBus

TEST_DATA_DIR = Path(__file__).parents[3] / "test_data"
CA_BUNDLE = str(TEST_DATA_DIR / "ca-bundle.pem")


@dataclass
class RoutingCase:
    name: str
    routing_key: str
    expected_stream: str


@pytest.mark.parametrize(
    "case",
    [
        RoutingCase(name="registry_event", routing_key="refresh.registry.branches", expected_stream="infrahub:events"),
        RoutingCase(
            name="rebased_branch_event",
            routing_key="refresh.registry.rebased_branch",
            expected_stream="infrahub:events",
        ),
        RoutingCase(
            name="settings_event", routing_key="refresh.settings.response_delay", expected_stream="infrahub:events"
        ),
        RoutingCase(name="git_broadcast_event", routing_key="refresh.git.fetch", expected_stream="infrahub:events"),
        RoutingCase(
            name="webhook_work_item", routing_key="refresh.webhook.configuration", expected_stream="infrahub:rpcs"
        ),
        RoutingCase(name="echo_work_item", routing_key="send.echo.request", expected_stream="infrahub:rpcs"),
        RoutingCase(name="git_file_work_item", routing_key="git.file.get", expected_stream="infrahub:rpcs"),
    ],
    ids=lambda case: case.name,
)
async def test_get_stream_for_routing_key(case: RoutingCase) -> None:
    bus = RedisMessageBus(
        component_type=ComponentType.API_SERVER,
        settings=BrokerSettings(driver=BrokerDriver.Redis, namespace="infrahub"),
    )
    assert bus._get_stream_for_routing_key(case.routing_key) == case.expected_stream


@dataclass
class TLSCase:
    name: str
    tls_insecure: bool
    expected_verify_mode: ssl.VerifyMode
    expected_check_hostname: bool


@pytest.mark.parametrize(
    "case",
    [
        TLSCase(
            name="verified",
            tls_insecure=False,
            expected_verify_mode=ssl.CERT_REQUIRED,
            expected_check_hostname=True,
        ),
        TLSCase(
            name="insecure",
            tls_insecure=True,
            expected_verify_mode=ssl.CERT_NONE,
            expected_check_hostname=False,
        ),
    ],
    ids=lambda case: case.name,
)
async def test_connection_applies_the_tls_settings(case: TLSCase) -> None:
    bus = RedisMessageBus(
        component_type=ComponentType.API_SERVER,
        settings=BrokerSettings(
            driver=BrokerDriver.Redis, tls_enabled=True, tls_insecure=case.tls_insecure, tls_ca_file=CA_BUNDLE
        ),
    )

    connection = bus._build_connection().connection_pool.make_connection()

    assert isinstance(connection, SSLConnection)
    context = connection.ssl_context.get()
    assert context.verify_mode == case.expected_verify_mode
    assert context.check_hostname is case.expected_check_hostname
    bundle_certs = ssl.create_default_context(cafile=CA_BUNDLE).get_ca_certs()
    assert bundle_certs
    assert all(cert in context.get_ca_certs() for cert in bundle_certs)
