"""Owners of single fields of a device through the API, on the full stack.

A relationship without peers gets its own owners, an attribute is set to no
owner, and the relationship then inherits again from its device. The test
opens no page. All work happens on a throwaway branch, so only the base schema
is needed.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

import pytest
from helpers import generate_random_branch_name

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from helpers import BranchAPI
    from infrahub_sdk import InfrahubClient

NODE_OWNER_GROUP = "device-owners-e2e"
FIELD_OWNER_GROUP = "interfaces-owners-e2e"

UPDATE_DEVICE = """
mutation UpdateDevice($id: String!, $metadata: NodeMetadataInput, $description: TextAttributeUpdate) {
  InfraDeviceUpdate(data: { id: $id, node_metadata: $metadata, description: $description }) {
    ok
  }
}
"""

OWNERSHIP = "ownership { state origin origin_node { id } owners { id display_label } }"

FIELDS_QUERY = f"""
query Fields($ids: [ID]) {{
  InfraDevice(ids: $ids) {{
    edges {{
      node {{
        name {{ {OWNERSHIP} }}
        description {{ value {OWNERSHIP} }}
        interfaces {{ count {OWNERSHIP} }}
      }}
    }}
  }}
}}
"""


def _ownership(state: str, origin: str, device_id: str, *owners: tuple[str, str]) -> dict[str, Any]:
    return {
        "state": state,
        "origin": origin,
        "origin_node": {"id": device_id},
        "owners": [{"id": owner_id, "display_label": name} for owner_id, name in owners],
    }


class TestFieldOwners:
    @pytest.fixture
    async def branch_name(self, branch_api: BranchAPI, schema_base: None) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("field-owners")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_fields_of_a_device_get_own_owners_no_owner_and_inherit_again(
        self, infrahub_client: InfrahubClient, branch_name: str
    ) -> None:
        client = infrahub_client

        async def update(variables: dict[str, Any]) -> None:
            response = await client.execute_graphql(
                query=UPDATE_DEVICE, variables={"id": device.id} | variables, branch_name=branch_name
            )
            assert response == {"InfraDeviceUpdate": {"ok": True}}

        async def fields() -> dict[str, Any]:
            response = await client.execute_graphql(
                query=FIELDS_QUERY, variables={"ids": [device.id]}, branch_name=branch_name
            )
            return response["InfraDevice"]["edges"][0]["node"]

        node_owner = await client.create(branch=branch_name, kind="CoreAccountGroup", data={"name": NODE_OWNER_GROUP})
        await node_owner.save()
        field_owner = await client.create(branch=branch_name, kind="CoreAccountGroup", data={"name": FIELD_OWNER_GROUP})
        await field_owner.save()
        device = await client.create(
            branch=branch_name,
            kind="InfraDevice",
            data={"name": "field-owners-device", "type": "7280R3", "role": "edge"},
        )
        await device.save()
        await update({"metadata": {"owners": [{"id": node_owner.id}]}})
        from_device = _ownership("INHERIT", "NODE", device.id, (node_owner.id, NODE_OWNER_GROUP))
        assert await fields() == {
            "name": {"ownership": from_device},
            "description": {"value": None, "ownership": from_device},
            "interfaces": {"count": 0, "ownership": from_device},
        }

        # A relationship without peers gets its own owners, and an attribute gets no owner next to its value.
        await update(
            {
                "metadata": {"field_owners": [{"field": "interfaces", "owners": [{"id": field_owner.id}]}]},
                "description": {"value": "spare", "owners": []},
            }
        )
        with_own_states = {
            "name": {"ownership": from_device},
            "description": {"value": "spare", "ownership": _ownership("NO_OWNER", "SELF", device.id)},
            "interfaces": {
                "count": 0,
                "ownership": _ownership("OWNERS", "SELF", device.id, (field_owner.id, FIELD_OWNER_GROUP)),
            },
        }
        assert await fields() == with_own_states

        # The relationship inherits again from its device, and the attribute keeps its own state.
        await update({"metadata": {"field_owners": [{"field": "interfaces", "owners": None}]}})
        assert await fields() == with_own_states | {"interfaces": {"count": 0, "ownership": from_device}}
