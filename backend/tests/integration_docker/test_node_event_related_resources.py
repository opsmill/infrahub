"""Node-created events must be recorded even for nodes with large relationships.

The Prefect API rejects any event whose related resources exceed the configured
maximum (``PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES``, 500 in the
Infrahub image). A node mutation event lists every cardinality-many
relationship peer in its related resources, so creating a node with a few
hundred peers (e.g. a trunk interface carrying a large VLAN range) produces an
event too large to record: the mutation succeeds but the event silently never
lands in the event store, and the node has no activity log.
"""

from __future__ import annotations

import time
from asyncio import sleep
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml
from infrahub_sdk.testing.docker import TestInfrahubDockerClient

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

CURRENT_DIRECTORY = Path(__file__).parent.resolve()

# Each peer adds two related resources to the node-created event, so 300 peers
# put the event above the 500 maximum while the single-VLAN control interface
# stays far below it.
TAGGED_VLAN_COUNT = 300

EVENT_WAIT_SECONDS = 120

NODE_CREATED_EVENT_COUNT_QUERY = """
query NodeCreatedEventCount($node_ids: [String!]) {
  InfrahubEvent(event_type: ["infrahub.node.created"], primary_node__ids: $node_ids) {
    count
  }
}
"""


async def created_event_recorded(client: InfrahubClient, node_id: str) -> bool:
    """Poll the event store until the created event of the node shows up."""
    deadline = time.monotonic() + EVENT_WAIT_SECONDS
    while time.monotonic() < deadline:
        result = await client.execute_graphql(query=NODE_CREATED_EVENT_COUNT_QUERY, variables={"node_ids": [node_id]})
        if result["InfrahubEvent"]["count"] > 0:
            return True
        await sleep(1)
    return False


class TestNodeEventRelatedResources(TestInfrahubDockerClient):
    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    @pytest.fixture(scope="class")
    def schema_vlan_trunk_interface(self) -> dict:
        return yaml.safe_load(
            Path(CURRENT_DIRECTORY / "test_files/vlan_and_trunk_interface_schema.yml").read_text(encoding="utf-8")
        )

    async def test_load_schema(self, client: InfrahubClient, schema_vlan_trunk_interface: dict) -> None:
        response = await client.schema.load(schemas=[schema_vlan_trunk_interface], wait_until_converged=True)
        assert response.schema_updated

    async def test_created_event_recorded_for_node_with_large_relationship(self, client: InfrahubClient) -> None:
        # The VLAN range the trunk interface will tag.
        vlan_batch = await client.create_batch()
        vlans = []
        for idx in range(TAGGED_VLAN_COUNT):
            vlan = await client.create(kind="TestingEventVlan", name=f"vlan-{idx}")
            vlan_batch.add(task=vlan.save, node=vlan)
            vlans.append(vlan)
        async for _ in vlan_batch.execute():
            pass

        # Control: an interface tagging a single VLAN, proving the event
        # pipeline (emission, ingestion, query) works for this mutation shape.
        small_interface = await client.create(
            kind="TestingEventInterface", name="Ethernet1", tagged_vlans=[vlans[0].id]
        )
        await small_interface.save()

        # The reproduction target: a trunk interface tagging the whole range.
        large_interface = await client.create(
            kind="TestingEventInterface", name="Ethernet2", tagged_vlans=[vlan.id for vlan in vlans]
        )
        await large_interface.save()

        assert await created_event_recorded(client=client, node_id=small_interface.id), (
            "the created event of the single-VLAN interface was never recorded"
        )
        assert await created_event_recorded(client=client, node_id=large_interface.id), (
            f"the created event of the interface tagging {TAGGED_VLAN_COUNT} VLANs was never recorded"
        )
