from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.components import ComponentType
from infrahub.config import BrokerDriver, BrokerSettings
from infrahub.services.adapters.message_bus.redis import RedisMessageBus


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
