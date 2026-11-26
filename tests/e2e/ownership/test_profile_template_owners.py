"""Owners that a profile and an object template give to devices, through the API, on the full stack.

A device takes its owners from its profile. A device created from an object
template gets a copy of the owners that the template gives, and a profile
replaces that copy. The test opens no page. All work happens on a throwaway
branch, so only the base schema is needed.
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

PROFILE_OWNER_GROUP = "profile-owners-e2e"
TEMPLATE_OWNER_GROUP = "template-owners-e2e"

SET_GIVEN_OWNERS = """
mutation SetGivenOwners($id: String!, $owners: [MetadataNodeInput!]) {
  %(kind)sUpdate(data: { id: $id, node_metadata: { target_owners: $owners } }) {
    ok
  }
}
"""

CREATE_DEVICE_FROM_TEMPLATE = """
mutation CreateDeviceFromTemplate($name: String!, $template: String!) {
  InfraDeviceCreate(data: { name: { value: $name }, object_template: { id: $template } }) {
    object { id }
  }
}
"""

SET_DEVICE_PROFILES = """
mutation SetDeviceProfiles($id: String!, $profiles: [RelatedNodeInput]) {
  InfraDeviceUpdate(data: { id: $id, profiles: $profiles }) {
    ok
  }
}
"""

GIVEN_OWNERS_QUERY = """
query GivenOwners($ids: [ID]) {
  %(kind)s(ids: $ids) {
    edges {
      node_metadata { target_ownership { state owners { id } } }
    }
  }
}
"""

OWNERSHIP_QUERY = """
query Ownership($ids: [ID]) {
  InfraDevice(ids: $ids) {
    edges {
      node { id }
      node_metadata {
        ownership {
          state
          origin
          origin_node { id kind is_deleted }
          owners { id kind display_label hfid is_deleted }
        }
      }
    }
  }
}
"""

OWNER_FILTER_QUERY = """
query OwnedBy($owners: [ID]) {
  InfraDevice(node_metadata__owners__ids: $owners) {
    edges { node { id } }
  }
}
"""


def _owner(group_id: str, name: str) -> dict[str, Any]:
    return {"id": group_id, "kind": "CoreAccountGroup", "display_label": name, "hfid": [name], "is_deleted": False}


class TestProfileTemplateOwners:
    @pytest.fixture
    async def branch_name(self, branch_api: BranchAPI, schema_base: None) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("profile-template-owners")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_profile_and_template_give_owners_to_devices(
        self, infrahub_client: InfrahubClient, branch_name: str
    ) -> None:
        client = infrahub_client

        async def ownerships(*device_ids: str) -> dict[str, dict[str, Any]]:
            response = await client.execute_graphql(
                query=OWNERSHIP_QUERY, variables={"ids": list(device_ids)}, branch_name=branch_name
            )
            return {edge["node"]["id"]: edge["node_metadata"]["ownership"] for edge in response["InfraDevice"]["edges"]}

        async def owned_by(group_id: str) -> list[str]:
            response = await client.execute_graphql(
                query=OWNER_FILTER_QUERY, variables={"owners": [group_id]}, branch_name=branch_name
            )
            return sorted(edge["node"]["id"] for edge in response["InfraDevice"]["edges"])

        profile_owner = await client.create(
            branch=branch_name, kind="CoreAccountGroup", data={"name": PROFILE_OWNER_GROUP}
        )
        await profile_owner.save()
        template_owner = await client.create(
            branch=branch_name, kind="CoreAccountGroup", data={"name": TEMPLATE_OWNER_GROUP}
        )
        await template_owner.save()
        profile = await client.create(
            branch=branch_name, kind="ProfileInfraDevice", data={"profile_name": "owners-profile-e2e"}
        )
        await profile.save()
        template = await client.create(
            branch=branch_name,
            kind="TemplateInfraDevice",
            data={"template_name": "owners-template-e2e", "type": "7280R3", "role": "leaf"},
        )
        await template.save()
        for kind, giver_id, owner_id in (
            ("ProfileInfraDevice", profile.id, profile_owner.id),
            ("TemplateInfraDevice", template.id, template_owner.id),
        ):
            response = await client.execute_graphql(
                query=SET_GIVEN_OWNERS % {"kind": kind},
                variables={"id": giver_id, "owners": [{"id": owner_id}]},
                branch_name=branch_name,
            )
            assert response == {f"{kind}Update": {"ok": True}}
            response = await client.execute_graphql(
                query=GIVEN_OWNERS_QUERY % {"kind": kind}, variables={"ids": [giver_id]}, branch_name=branch_name
            )
            assert response[kind]["edges"] == [
                {"node_metadata": {"target_ownership": {"state": "OWNERS", "owners": [{"id": owner_id}]}}}
            ]

        # A device takes the owners that its profile gives.
        profile_device = await client.create(
            branch=branch_name,
            kind="InfraDevice",
            data={"name": "profile-owned-device", "type": "7280R3", "role": "edge", "profiles": [profile.id]},
        )
        await profile_device.save()
        # A device created from the template gets a copy of the owners that the template gives.
        response = await client.execute_graphql(
            query=CREATE_DEVICE_FROM_TEMPLATE,
            variables={"name": "template-owned-device", "template": template.id},
            branch_name=branch_name,
        )
        template_device_id: str = response["InfraDeviceCreate"]["object"]["id"]

        from_profile = {
            "state": "INHERIT",
            "origin": "PROFILE",
            "origin_node": {"id": profile.id, "kind": "ProfileInfraDevice", "is_deleted": False},
            "owners": [_owner(profile_owner.id, PROFILE_OWNER_GROUP)],
        }
        assert await ownerships(profile_device.id, template_device_id) == {
            profile_device.id: from_profile,
            template_device_id: {
                "state": "INHERIT",
                "origin": "TEMPLATE",
                "origin_node": {"id": template.id, "kind": "TemplateInfraDevice", "is_deleted": False},
                "owners": [_owner(template_owner.id, TEMPLATE_OWNER_GROUP)],
            },
        }
        assert await owned_by(profile_owner.id) == [profile_device.id]
        assert await owned_by(template_owner.id) == [template_device_id]

        # A profile replaces the owners that came from the template.
        response = await client.execute_graphql(
            query=SET_DEVICE_PROFILES,
            variables={"id": template_device_id, "profiles": [{"id": profile.id}]},
            branch_name=branch_name,
        )
        assert response == {"InfraDeviceUpdate": {"ok": True}}

        assert await ownerships(template_device_id) == {template_device_id: from_profile}
        assert await owned_by(profile_owner.id) == sorted([profile_device.id, template_device_id])
        assert await owned_by(template_owner.id) == []
