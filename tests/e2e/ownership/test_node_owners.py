"""Owners of a node through the API, on the full stack.

A device gets owners, its interface inherits them, a list filter by owner finds
the device and the interface, and the `owner` field of an attribute still reads
the owner of that attribute. The test opens no page. All work happens on a
throwaway branch, so only the base schema is needed.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from helpers import BranchAPI
    from infrahub_sdk import InfrahubClient

NODE_OWNER_GROUP = "node-owners-e2e"
ATTRIBUTE_OWNER_GROUP = "attribute-owner-e2e"

SET_DEVICE_OWNERS = """
mutation SetDeviceOwners($id: String!, $owners: [MetadataNodeInput!]) {
  InfraDeviceUpdate(data: { id: $id, node_metadata: { owners: $owners } }) {
    ok
  }
}
"""

OWNERSHIP_QUERY = """
query Ownership($device_ids: [ID], $interface_ids: [ID]) {
  InfraDevice(ids: $device_ids) {
    edges {
      node { id }
      node_metadata { ownership { ...OwnershipFields } }
    }
  }
  InfraInterfaceL3(ids: $interface_ids) {
    edges {
      node { id }
      node_metadata { ownership { ...OwnershipFields } }
    }
  }
}

fragment OwnershipFields on InfrahubOwnership {
  state
  origin
  origin_node { id kind is_deleted }
  owners { id kind display_label hfid is_deleted }
}
"""

OWNER_FILTER_QUERY = """
query OwnedBy($owners: [ID]) {
  InfraDevice(node_metadata__owners__ids: $owners) {
    count
    edges { node { id } }
  }
  InfraInterfaceL3(node_metadata__owners__ids: $owners) {
    count
    edges { node { id } }
  }
}
"""

ATTRIBUTE_OWNER_QUERY = """
query AttributeOwner($ids: [ID]) {
  InfraDevice(ids: $ids) {
    edges {
      node {
        name { value owner { id display_label } }
        type { value owner { id } }
      }
    }
  }
}
"""


class TestNodeOwners:
    @pytest.fixture
    async def branch_name(self, branch_api: BranchAPI, schema_base: None) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("node-owners")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_interface_inherits_the_owners_set_on_its_device(
        self, infrahub_client: InfrahubClient, branch_name: str
    ) -> None:
        client = infrahub_client
        node_owner = await client.create(branch=branch_name, kind="CoreAccountGroup", data={"name": NODE_OWNER_GROUP})
        await node_owner.save()
        attribute_owner = await client.create(
            branch=branch_name, kind="CoreAccountGroup", data={"name": ATTRIBUTE_OWNER_GROUP}
        )
        await attribute_owner.save()
        interface_ids: dict[str, str] = {}
        device_ids: dict[str, str] = {}
        for device_name in ("owned-device", "other-device"):
            device = await client.create(
                branch=branch_name,
                kind="InfraDevice",
                data={"name": {"value": device_name, "owner": attribute_owner.id}, "type": "7280R3", "role": "edge"},
            )
            await device.save()
            interface = await client.create(
                branch=branch_name,
                kind="InfraInterfaceL3",
                data={"name": "Ethernet1", "speed": 1000, "device": device.id},
            )
            await interface.save()
            device_ids[device_name] = device.id
            interface_ids[device_name] = interface.id
        owned_device_id = device_ids["owned-device"]
        owned_interface_id = interface_ids["owned-device"]

        response = await client.execute_graphql(
            query=SET_DEVICE_OWNERS,
            variables={"id": owned_device_id, "owners": [{"id": node_owner.id}]},
            branch_name=branch_name,
        )
        assert response == {"InfraDeviceUpdate": {"ok": True}}

        # The interface inherits the owners of its device, and the other device has none.
        owners = [
            {
                "id": node_owner.id,
                "kind": "CoreAccountGroup",
                "display_label": NODE_OWNER_GROUP,
                "hfid": [NODE_OWNER_GROUP],
                "is_deleted": False,
            }
        ]
        origin_node = {"id": owned_device_id, "kind": "InfraDevice", "is_deleted": False}
        no_ownership = {"state": "INHERIT", "origin": None, "origin_node": None, "owners": []}
        response = await client.execute_graphql(
            query=OWNERSHIP_QUERY,
            variables={"device_ids": list(device_ids.values()), "interface_ids": list(interface_ids.values())},
            branch_name=branch_name,
        )
        ownerships = {
            edge["node"]["id"]: edge["node_metadata"]["ownership"]
            for kind in ("InfraDevice", "InfraInterfaceL3")
            for edge in response[kind]["edges"]
        }
        assert ownerships == {
            owned_device_id: {"state": "OWNERS", "origin": "SELF", "origin_node": origin_node, "owners": owners},
            owned_interface_id: {"state": "INHERIT", "origin": "PARENT", "origin_node": origin_node, "owners": owners},
            device_ids["other-device"]: no_ownership,
            interface_ids["other-device"]: no_ownership,
        }

        # A filter by owner finds the device, and the interface that inherits from it.
        response = await client.execute_graphql(
            query=OWNER_FILTER_QUERY, variables={"owners": [node_owner.id]}, branch_name=branch_name
        )
        assert response == {
            "InfraDevice": {"count": 1, "edges": [{"node": {"id": owned_device_id}}]},
            "InfraInterfaceL3": {"count": 1, "edges": [{"node": {"id": owned_interface_id}}]},
        }

        # The owner of an attribute is separate from the owners of its node.
        response = await client.execute_graphql(
            query=ATTRIBUTE_OWNER_QUERY, variables={"ids": [owned_device_id]}, branch_name=branch_name
        )
        assert response == {
            "InfraDevice": {
                "edges": [
                    {
                        "node": {
                            "name": {
                                "value": "owned-device",
                                "owner": {"id": attribute_owner.id, "display_label": ATTRIBUTE_OWNER_GROUP},
                            },
                            "type": {"value": "7280R3", "owner": None},
                        }
                    }
                ]
            }
        }
