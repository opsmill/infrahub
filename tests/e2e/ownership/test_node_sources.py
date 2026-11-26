"""Sources of a node through the API, on the full stack.

A device gets two sources at its creation, a list query returns both, and a list
filter by one source finds the devices of that source with the correct count.
The test opens no page. All work happens on a throwaway branch, so only the base
schema is needed.
"""

from __future__ import annotations

import contextlib
from operator import itemgetter
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from helpers import BranchAPI
    from infrahub_sdk import InfrahubClient

SYNC_SOURCE_GROUP = "cmdb-sync-e2e"
DATA_SOURCE_GROUP = "infra-data-e2e"

CREATE_DEVICE = """
mutation CreateDevice($name: String!, $sources: [MetadataNodeInput!]) {
  InfraDeviceCreate(
    data: {
      name: { value: $name }
      type: { value: "7280R3" }
      role: { value: "edge" }
      node_metadata: { sources: $sources }
    }
  ) {
    object { id }
  }
}
"""

SOURCES_QUERY = """
query Sources($ids: [ID]) {
  InfraDevice(ids: $ids) {
    edges {
      node { id }
      node_metadata { sources { id kind display_label hfid is_deleted } }
    }
  }
}
"""

SOURCE_FILTER_QUERY = """
query FromSource($sources: [ID]) {
  InfraDevice(node_metadata__sources__ids: $sources) {
    count
    edges { node { id } }
  }
}
"""


class TestNodeSources:
    @pytest.fixture
    async def branch_name(self, branch_api: BranchAPI, schema_base: None) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("node-sources")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_device_with_two_sources_is_in_the_list_of_each_source(
        self, infrahub_client: InfrahubClient, branch_name: str
    ) -> None:
        client = infrahub_client
        sources: dict[str, dict[str, object]] = {}
        for name in (SYNC_SOURCE_GROUP, DATA_SOURCE_GROUP):
            group = await client.create(branch=branch_name, kind="CoreAccountGroup", data={"name": name})
            await group.save()
            sources[name] = {
                "id": group.id,
                "kind": "CoreAccountGroup",
                "display_label": name,
                "hfid": [name],
                "is_deleted": False,
            }
        sync_id, data_id = sources[SYNC_SOURCE_GROUP]["id"], sources[DATA_SOURCE_GROUP]["id"]
        device_sources = {
            "device-two-sources": [{"id": sync_id}, {"kind": "CoreAccountGroup", "hfid": [DATA_SOURCE_GROUP]}],
            "device-one-source": [{"id": sync_id}],
            "device-no-source": None,
        }
        device_ids: dict[str, str] = {}
        for device_name, device_source in device_sources.items():
            response = await client.execute_graphql(
                query=CREATE_DEVICE, variables={"name": device_name, "sources": device_source}, branch_name=branch_name
            )
            device_ids[device_name] = response["InfraDeviceCreate"]["object"]["id"]

        # A list query returns both sources of the device.
        response = await client.execute_graphql(
            query=SOURCES_QUERY, variables={"ids": list(device_ids.values())}, branch_name=branch_name
        )
        assert {edge["node"]["id"]: edge["node_metadata"]["sources"] for edge in response["InfraDevice"]["edges"]} == {
            device_ids["device-two-sources"]: sorted(sources.values(), key=itemgetter("id")),
            device_ids["device-one-source"]: [sources[SYNC_SOURCE_GROUP]],
            device_ids["device-no-source"]: [],
        }

        # A filter by one source finds each device of that source, with the count.
        response = await client.execute_graphql(
            query=SOURCE_FILTER_QUERY, variables={"sources": [sync_id]}, branch_name=branch_name
        )
        assert response["InfraDevice"]["count"] == 2
        assert {edge["node"]["id"] for edge in response["InfraDevice"]["edges"]} == {
            device_ids["device-two-sources"],
            device_ids["device-one-source"],
        }
        response = await client.execute_graphql(
            query=SOURCE_FILTER_QUERY, variables={"sources": [data_id]}, branch_name=branch_name
        )
        assert response == {"InfraDevice": {"count": 1, "edges": [{"node": {"id": device_ids["device-two-sources"]}}]}}

        # The default branch does not have the sources that the other branch stores.
        response = await client.execute_graphql(query=SOURCE_FILTER_QUERY, variables={"sources": [sync_id, data_id]})
        assert response == {"InfraDevice": {"count": 0, "edges": []}}
