from __future__ import annotations

from asyncio import sleep
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml
from infrahub_sdk.testing.docker import TestInfrahubDockerClient

from infrahub.trigger.constants import NAME_SEPARATOR
from infrahub.trigger.models import TriggerType
from infrahub.trigger.setup import gather_all_automations

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.node import RelatedNode, RelationshipManager
    from prefect.client.orchestration import PrefectClient

CURRENT_DIRECTORY = Path(__file__).parent.resolve()


class TestProfiles(TestInfrahubDockerClient):
    @pytest.fixture(scope="class")
    def schema_device(self) -> dict:
        with Path(CURRENT_DIRECTORY / "test_files/profile_device.yml").open(encoding="utf-8") as file:
            return yaml.safe_load(file.read())

    async def wait_until_profile_automations_are_configured(
        self, profile_kind: str, client: PrefectClient, max_retries: int = 30
    ) -> None:
        """Wait until the profile refresh automation for the given kind is configured."""
        expected_prefix = f"{TriggerType.PROFILE.value}{NAME_SEPARATOR}"

        for _ in range(max_retries):
            automations = await gather_all_automations(client=client)
            profile_automations = [a for a in automations if a.name.startswith(expected_prefix)]
            # Check if any automation is for our profile kind
            matching_automations = [a for a in profile_automations if profile_kind in a.name]
            if matching_automations:
                return
            await sleep(1)

        pytest.fail(f"Profile automation for {profile_kind} was not configured within {max_retries} seconds")

    async def wait_for_attribute_value(
        self,
        client: InfrahubClient,
        kind: str,
        node_id: str,
        attribute: str,
        expected_value: str | int | None,
        max_retries: int = 20,
    ) -> None:
        for _ in range(max_retries):
            node = await client.get(kind=kind, id=node_id, property=True)
            current_value = getattr(node, attribute).value
            if current_value == expected_value:
                return
            await sleep(1)

        node = await client.get(kind=kind, id=node_id, property=True)
        current_value = getattr(node, attribute).value
        pytest.fail(f"Expected {attribute}={expected_value} but got {current_value} after {max_retries} seconds")

    async def wait_for_relationship_peer(
        self,
        client: InfrahubClient,
        kind: str,
        node_id: str,
        relationship: str,
        expected_peer_id: str | None,
        max_retries: int = 20,
    ) -> None:
        for _ in range(max_retries):
            node = await client.get(kind=kind, id=node_id, property=True, include=[relationship])
            rel: RelatedNode = getattr(node, relationship)

            current_peer_id = rel.id
            if current_peer_id == expected_peer_id:
                return
            await sleep(1)

        node = await client.get(kind=kind, id=node_id, property=True, include=[relationship])
        rel: RelatedNode = getattr(node, relationship)
        pytest.fail(f"Expected {relationship} peer_id={expected_peer_id} but got {rel.id} after {max_retries} seconds")

    async def wait_for_relationship_peers(
        self,
        client: InfrahubClient,
        kind: str,
        node_id: str,
        relationship: str,
        expected_peer_ids: set[str],
        max_retries: int = 20,
    ) -> None:
        for _ in range(max_retries):
            node = await client.get(kind=kind, id=node_id, property=True, include=[relationship])
            rel: RelationshipManager = getattr(node, relationship)
            current_peer_ids = set(rel.peer_ids) if rel.peer_ids else set()
            if current_peer_ids == expected_peer_ids:
                return
            await sleep(1)

        node = await client.get(kind=kind, id=node_id, property=True, include=[relationship])
        rel: RelationshipManager = getattr(node, relationship)
        pytest.fail(
            f"Expected {relationship} peer_ids={expected_peer_ids} but got {set(rel.peer_ids) if rel.peer_ids else set()} after {max_retries} seconds"
        )

    async def test_load_schema(self, client: InfrahubClient, schema_device: dict) -> None:
        """Load the device schema which will generate a profile schema."""
        response = await client.schema.load(schemas=[schema_device], wait_until_converged=True)
        assert response.schema_updated
        assert await client.schema.in_sync()

    async def test_profile_attribute_update_triggers_refresh(self, client: InfrahubClient) -> None:
        device = await client.create(kind="TestingDevice", name="device-1")
        await device.save()

        device_initial = await client.get(kind="TestingDevice", id=device.id)
        assert device_initial.height.value is None
        assert not device_initial.height.is_from_profile
        assert device_initial.part_number.value is None
        assert not device_initial.part_number.is_from_profile

        profile = await client.create(
            kind="ProfileTestingDevice",
            profile_name="test-profile",
            profile_priority=1000,
            height=42,
            part_number="PN-001",
            related_nodes=[device.id],
        )
        await profile.save()

        await self.wait_for_attribute_value(
            client=client, kind="TestingDevice", node_id=device.id, attribute="height", expected_value=42
        )

        device_with_profile = await client.get(kind="TestingDevice", id=device.id, property=True)
        assert device_with_profile.height.value == 42
        assert device_with_profile.height.is_from_profile
        assert device_with_profile.part_number.value == "PN-001"
        assert device_with_profile.part_number.is_from_profile

        profile_to_update = await client.get(kind="ProfileTestingDevice", id=profile.id)
        profile_to_update.height.value = 100
        profile_to_update.part_number.value = "PN-002-UPDATED"
        await profile_to_update.save()

        await self.wait_for_attribute_value(
            client=client, kind="TestingDevice", node_id=device.id, attribute="height", expected_value=100
        )

        device_with_updated_profile = await client.get(kind="TestingDevice", id=device.id, property=True)
        assert device_with_updated_profile.height.value == 100
        assert device_with_updated_profile.height.is_from_profile
        assert device_with_updated_profile.part_number.value == "PN-002-UPDATED"
        assert device_with_updated_profile.part_number.is_from_profile

    async def test_profile_priority_change_triggers_refresh(self, client: InfrahubClient) -> None:
        device = await client.create(kind="TestingDevice", name="device-2")
        await device.save()

        profile_low = await client.create(
            kind="ProfileTestingDevice",
            profile_name="profile-low-priority",
            profile_priority=2000,
            weight=50,
            related_nodes=[device.id],
        )
        await profile_low.save()

        profile_high = await client.create(
            kind="ProfileTestingDevice",
            profile_name="profile-high-priority",
            profile_priority=1000,
            weight=100,
            related_nodes=[device.id],
        )
        await profile_high.save()

        await self.wait_for_attribute_value(
            client=client, kind="TestingDevice", node_id=device.id, attribute="weight", expected_value=100
        )

        device_with_profiles = await client.get(kind="TestingDevice", id=device.id, property=True)
        assert device_with_profiles.weight.value == 100
        assert device_with_profiles.weight.source.id == profile_high.id

        profile_low_update = await client.get(kind="ProfileTestingDevice", id=profile_low.id)
        profile_low_update.profile_priority.value = 500
        await profile_low_update.save()

        await self.wait_for_attribute_value(
            client=client, kind="TestingDevice", node_id=device.id, attribute="weight", expected_value=50
        )

        device_updated = await client.get(kind="TestingDevice", id=device.id, property=True)
        assert device_updated.weight.value == 50
        assert device_updated.weight.source.id == profile_low.id

    async def test_profile_delete_triggers_refresh(self, client: InfrahubClient) -> None:
        device = await client.create(kind="TestingDevice", name="device-3")
        await device.save()

        profile = await client.create(
            kind="ProfileTestingDevice",
            profile_name="profile-to-delete",
            profile_priority=1000,
            height=200,
            related_nodes=[device.id],
        )
        await profile.save()

        await self.wait_for_attribute_value(
            client=client, kind="TestingDevice", node_id=device.id, attribute="height", expected_value=200
        )

        device_with_profile = await client.get(kind="TestingDevice", id=device.id, property=True)
        assert device_with_profile.height.value == 200
        assert device_with_profile.height.is_from_profile

        profile_to_delete = await client.get(kind="ProfileTestingDevice", id=profile.id)
        await profile_to_delete.delete()

        await self.wait_for_attribute_value(
            client=client, kind="TestingDevice", node_id=device.id, attribute="height", expected_value=None
        )
        device_after_delete = await client.get(kind="TestingDevice", id=device.id, property=True)
        assert device_after_delete.height.value is None
        assert not device_after_delete.height.is_from_profile

    async def test_remove_node_from_profile_triggers_refresh(self, client: InfrahubClient) -> None:
        device = await client.create(kind="TestingDevice", name="device-4")
        await device.save()

        profile = await client.create(
            kind="ProfileTestingDevice",
            profile_name="profile-remove-node",
            profile_priority=1000,
            height=300,
            related_nodes=[device.id],
        )
        await profile.save()

        await self.wait_for_attribute_value(
            client=client, kind="TestingDevice", node_id=device.id, attribute="height", expected_value=300
        )

        device_with_profile = await client.get(kind="TestingDevice", id=device.id, property=True)
        assert device_with_profile.height.value == 300
        assert device_with_profile.height.is_from_profile

        profile_to_update = await client.get(kind="ProfileTestingDevice", id=profile.id, prefetch_relationships=True)
        await profile_to_update.related_nodes.fetch()
        profile_to_update.related_nodes.remove(device.id)
        await profile_to_update.save()

        await self.wait_for_attribute_value(
            client=client, kind="TestingDevice", node_id=device.id, attribute="height", expected_value=None
        )

        device_after_removal = await client.get(kind="TestingDevice", id=device.id, property=True)
        assert device_after_removal.height.value is None
        assert not device_after_removal.height.is_from_profile

    async def test_profile_relationship_cardinality_one_update(self, client: InfrahubClient) -> None:
        manufacturer1 = await client.create(kind="TestingManufacturer", name="Manufacturer-1", country="France")
        await manufacturer1.save()
        manufacturer2 = await client.create(kind="TestingManufacturer", name="Manufacturer-2", country="Germany")
        await manufacturer2.save()

        device = await client.create(kind="TestingDevice", name="device-rel-1")
        await device.save()

        device_initial = await client.get(kind="TestingDevice", id=device.id, property=True, include=["manufacturer"])
        assert not device_initial.manufacturer.id

        profile = await client.create(
            kind="ProfileTestingDevice",
            profile_name="profile-with-manufacturer",
            profile_priority=1000,
            manufacturer=manufacturer1,
            related_nodes=[device],
        )
        await profile.save()

        await self.wait_for_relationship_peer(
            client=client,
            kind="TestingDevice",
            node_id=device.id,
            relationship="manufacturer",
            expected_peer_id=manufacturer1.id,
        )

        profile_to_update = await client.get(kind="ProfileTestingDevice", id=profile.id, include=["manufacturer"])
        profile_to_update.manufacturer = manufacturer2
        await profile_to_update.save()

        await self.wait_for_relationship_peer(
            client=client,
            kind="TestingDevice",
            node_id=device.id,
            relationship="manufacturer",
            expected_peer_id=manufacturer2.id,
        )

    async def test_profile_relationship_cardinality_many_update(self, client: InfrahubClient) -> None:
        tenant1 = await client.create(kind="TestingTenant", name="Tenant-1", description="First tenant")
        await tenant1.save()
        tenant2 = await client.create(kind="TestingTenant", name="Tenant-2", description="Second tenant")
        await tenant2.save()
        tenant3 = await client.create(kind="TestingTenant", name="Tenant-3", description="Third tenant")
        await tenant3.save()

        device = await client.create(kind="TestingDevice", name="device-rel-many-1")
        await device.save()

        device_initial = await client.get(
            kind="TestingDevice", id=device.id, property=True, prefetch_relationships=True
        )
        assert not device_initial.tenants.peer_ids

        profile = await client.create(
            kind="ProfileTestingDevice",
            profile_name="profile-with-tenants",
            profile_priority=1000,
            tenants=[tenant1, tenant2],
            related_nodes=[device],
        )
        await profile.save()

        await self.wait_for_relationship_peers(
            client=client,
            kind="TestingDevice",
            node_id=device.id,
            relationship="tenants",
            expected_peer_ids={tenant1.id, tenant2.id},
        )

        profile_to_update = await client.get(kind="ProfileTestingDevice", id=profile.id, include=["tenants"])
        await profile_to_update.tenants.fetch()
        profile_to_update.tenants.remove(tenant1.id)
        profile_to_update.tenants.add(tenant3.id)
        await profile_to_update.save()

        await self.wait_for_relationship_peers(
            client=client,
            kind="TestingDevice",
            node_id=device.id,
            relationship="tenants",
            expected_peer_ids={tenant2.id, tenant3.id},
        )

    async def test_profile_relationship_priority(self, client: InfrahubClient) -> None:
        manufacturer_low = await client.create(kind="TestingManufacturer", name="Manufacturer-Low", country="Japan")
        await manufacturer_low.save()
        manufacturer_high = await client.create(kind="TestingManufacturer", name="Manufacturer-High", country="Korea")
        await manufacturer_high.save()

        device = await client.create(kind="TestingDevice", name="device-rel-priority")
        await device.save()

        profile_low = await client.create(
            kind="ProfileTestingDevice",
            profile_name="profile-mfr-low-prio",
            profile_priority=2000,
            manufacturer=manufacturer_low,
            related_nodes=[device],
        )
        await profile_low.save()

        profile_high = await client.create(
            kind="ProfileTestingDevice",
            profile_name="profile-mfr-high-prio",
            profile_priority=1000,
            manufacturer=manufacturer_high,
            related_nodes=[device],
        )
        await profile_high.save()

        await self.wait_for_relationship_peer(
            client=client,
            kind="TestingDevice",
            node_id=device.id,
            relationship="manufacturer",
            expected_peer_id=manufacturer_high.id,
        )

        profile_low_update = await client.get(kind="ProfileTestingDevice", id=profile_low.id)
        profile_low_update.profile_priority.value = 500
        await profile_low_update.save()

        await self.wait_for_relationship_peer(
            client=client,
            kind="TestingDevice",
            node_id=device.id,
            relationship="manufacturer",
            expected_peer_id=manufacturer_low.id,
        )
