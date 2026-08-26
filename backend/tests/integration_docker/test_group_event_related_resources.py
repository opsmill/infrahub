"""Group member-added events must be recorded even when many members change at once.

The Prefect API rejects any event whose related resources exceed the configured
maximum (``PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES``, 500 in the Infrahub
image). A group mutation event lists every added member in its related
resources, so adding a few hundred members in a single mutation produced an
event too large to record: the mutation succeeded but the ``member_added``
event silently never landed in the event store, so the group's activity log was
missing and membership-driven automations never fired.
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

# Before consolidation each member added two related resources to the event, so
# 300 members put it above the 500 maximum (~247 members was already enough)
# while the single-member control group stayed far below it. After consolidation
# the same 300 members produce ~300 related resources, comfortably under the
# maximum, so the event is recorded again. The truncation cap itself is exercised
# by the unit tests, which push past the maximum.
MEMBER_COUNT = 300

EVENT_WAIT_SECONDS = 120

MEMBER_ADDED_EVENT_COUNT_QUERY = """
query MemberAddedEventCount($node_ids: [String!]) {
  InfrahubEvent(event_type: ["infrahub.group.member_added"], primary_node__ids: $node_ids) {
    count
  }
}
"""


async def member_added_event_recorded(client: InfrahubClient, group_id: str) -> bool:
    """Poll the event store until the member-added event of the group shows up."""
    deadline = time.monotonic() + EVENT_WAIT_SECONDS
    while time.monotonic() < deadline:
        result = await client.execute_graphql(query=MEMBER_ADDED_EVENT_COUNT_QUERY, variables={"node_ids": [group_id]})
        if result["InfrahubEvent"]["count"] > 0:
            return True
        await sleep(1)
    return False


class TestGroupEventRelatedResources(TestInfrahubDockerClient):
    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    @pytest.fixture(scope="class")
    def schema_group_member(self) -> dict:
        return yaml.safe_load(
            Path(CURRENT_DIRECTORY / "test_files/group_member_schema.yml").read_text(encoding="utf-8")
        )

    async def test_load_schema(self, client: InfrahubClient, schema_group_member: dict) -> None:
        response = await client.schema.load(schemas=[schema_group_member], wait_until_converged=True)
        assert response.schema_updated

    async def test_member_added_event_recorded_for_group_with_many_members(self, client: InfrahubClient) -> None:
        # The members the groups will contain.
        member_batch = await client.create_batch()
        members = []
        for idx in range(MEMBER_COUNT):
            member = await client.create(kind="TestingEventMember", name=f"member-{idx}")
            member_batch.add(task=member.save, node=member)
            members.append(member)
        async for _ in member_batch.execute():
            pass

        # Control: a group with a single member, proving the event pipeline
        # (emission, ingestion, query) works for this mutation shape.
        small_group = await client.create(kind="CoreStandardGroup", name="control-group", members=[members[0].id])
        await small_group.save()

        # The reproduction target: a group taking on the whole member set at once.
        large_group = await client.create(
            kind="CoreStandardGroup", name="large-group", members=[member.id for member in members]
        )
        await large_group.save()

        assert await member_added_event_recorded(client=client, group_id=small_group.id), (
            "the member_added event of the single-member group was never recorded"
        )
        assert await member_added_event_recorded(client=client, group_id=large_group.id), (
            f"the member_added event of the group taking on {MEMBER_COUNT} members was never recorded"
        )
