from __future__ import annotations

from asyncio import sleep
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.testing.docker import TestInfrahubDockerClient

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.node import InfrahubNode, RelatedNode, RelationshipManager

CURRENT_DIRECTORY = Path(__file__).parent.resolve()


class TestProfiles(TestInfrahubDockerClient):
    @pytest.fixture(scope="class")
    def schema_device(self) -> dict:
        with Path(CURRENT_DIRECTORY / "test_files/profile_device.yml").open(encoding="utf-8") as file:
            return yaml.safe_load(file.read())

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
        rel = getattr(node, relationship)
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
        rel = getattr(node, relationship)
        pytest.fail(
            f"Expected {relationship} peer_ids={expected_peer_ids} but got {set(rel.peer_ids) if rel.peer_ids else set()} after {max_retries} seconds"
        )

    async def _create_manufacturer(self, client: InfrahubClient, name: str, country: str = "USA") -> InfrahubNode:
        manufacturer = await client.create(kind="TestingManufacturer", name=name, country=country)
        await manufacturer.save()
        return manufacturer

    async def test_load_schema(self, client: InfrahubClient, schema_device: dict) -> None:
        response = await client.schema.load(schemas=[schema_device], wait_until_converged=True)
        assert response.schema_updated
        assert await client.schema.in_sync()

    async def test_profile_attribute_update_triggers_refresh(self, client: InfrahubClient) -> None:
        manufacturer = await self._create_manufacturer(client=client, name="Manufacturer-attr-update")
        device = await client.create(
            kind="TestingDevice", name="device-1", manufacturer=manufacturer, part_number="MF-PN-001"
        )
        await device.save()

        device_initial = await client.get(kind="TestingDevice", id=device.id)
        assert device_initial.height.value is None
        assert not device_initial.height.is_from_profile
        assert device_initial.part_number.value == "MF-PN-001"
        assert not device_initial.part_number.is_from_profile

        profile = await client.create(
            kind="ProfileTestingDevice",
            profile_name="test-profile",
            profile_priority=1000,
            height=42,
            related_nodes=[device.id],
        )
        await profile.save()

        await self.wait_for_attribute_value(
            client=client, kind="TestingDevice", node_id=device.id, attribute="height", expected_value=42
        )

        device_with_profile = await client.get(kind="TestingDevice", id=device.id, property=True)
        assert device_with_profile.height.value == 42
        assert device_with_profile.height.is_from_profile
        assert device_with_profile.part_number.value == "MF-PN-001"
        assert not device_with_profile.part_number.is_from_profile

        profile_to_update = await client.get(kind="ProfileTestingDevice", id=profile.id)
        profile_to_update.height.value = 100
        await profile_to_update.save()

        await self.wait_for_attribute_value(
            client=client, kind="TestingDevice", node_id=device.id, attribute="height", expected_value=100
        )

        device_with_updated_profile = await client.get(kind="TestingDevice", id=device.id, property=True)
        assert device_with_updated_profile.height.value == 100
        assert device_with_updated_profile.height.is_from_profile

    async def test_profile_priority_change_triggers_refresh(self, client: InfrahubClient) -> None:
        manufacturer = await self._create_manufacturer(client=client, name="Manufacturer-priority")
        device = await client.create(
            kind="TestingDevice", name="device-2", manufacturer=manufacturer, part_number="MF-PN-002"
        )
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
        manufacturer = await self._create_manufacturer(client=client, name="Manufacturer-delete")
        device = await client.create(
            kind="TestingDevice", name="device-3", manufacturer=manufacturer, part_number="MF-PN-003"
        )
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
        manufacturer = await self._create_manufacturer(client=client, name="Manufacturer-remove-node")
        device = await client.create(
            kind="TestingDevice", name="device-4", manufacturer=manufacturer, part_number="MF-PN-004"
        )
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
        manufacturer_initial = await self._create_manufacturer(client=client, name="Manufacturer-initial")
        manufacturer1 = await self._create_manufacturer(client=client, name="Manufacturer-rel-1", country="France")
        manufacturer2 = await self._create_manufacturer(client=client, name="Manufacturer-rel-2", country="Germany")

        device = await client.create(
            kind="TestingDevice", name="device-rel-1", manufacturer=manufacturer_initial, part_number="MF-PN-REL-1"
        )
        await device.save()

        device_initial = await client.get(kind="TestingDevice", id=device.id, property=True, include=["manufacturer"])
        assert device_initial.manufacturer.id == manufacturer_initial.id

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

        device_after_profile = await client.get(
            kind="TestingDevice", id=device.id, property=True, include=["manufacturer"]
        )
        assert device_after_profile.manufacturer.id == manufacturer1.id

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

        device_after_update = await client.get(
            kind="TestingDevice", id=device.id, property=True, include=["manufacturer"]
        )
        assert device_after_update.manufacturer.id == manufacturer2.id

    async def test_profile_relationship_cardinality_many_update(self, client: InfrahubClient) -> None:
        manufacturer = await self._create_manufacturer(client=client, name="Manufacturer-many")

        tenant1 = await client.create(kind="TestingTenant", name="Tenant-1", description="First tenant")
        await tenant1.save()
        tenant2 = await client.create(kind="TestingTenant", name="Tenant-2", description="Second tenant")
        await tenant2.save()
        tenant3 = await client.create(kind="TestingTenant", name="Tenant-3", description="Third tenant")
        await tenant3.save()

        device = await client.create(
            kind="TestingDevice", name="device-rel-many-1", manufacturer=manufacturer, part_number="MF-PN-MANY-1"
        )
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
        manufacturer_initial = await self._create_manufacturer(client=client, name="Manufacturer-prio-initial")
        manufacturer_low = await self._create_manufacturer(client=client, name="Manufacturer-Low", country="Japan")
        manufacturer_high = await self._create_manufacturer(client=client, name="Manufacturer-High", country="Korea")

        device = await client.create(
            kind="TestingDevice",
            name="device-rel-priority",
            manufacturer=manufacturer_initial,
            part_number="MF-PN-PRIO",
        )
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

        device_with_profiles = await client.get(
            kind="TestingDevice", id=device.id, property=True, include=["manufacturer"]
        )
        assert device_with_profiles.manufacturer.id == manufacturer_high.id

    async def test_cannot_delete_profile_when_device_inherits_required_attribute(self, client: InfrahubClient) -> None:
        manufacturer = await self._create_manufacturer(client=client, name="Manufacturer-constraint-attr")

        profile = await client.create(
            kind="ProfileTestingDevice",
            profile_name="profile-provides-part-number",
            profile_priority=1000,
            part_number="PROFILE-PN-001",
        )
        await profile.save()

        device = await client.create(
            kind="TestingDevice", name="device-constraint-attr-1", manufacturer=manufacturer, profiles=[profile]
        )
        await device.save()

        await self.wait_for_attribute_value(
            client=client,
            kind="TestingDevice",
            node_id=device.id,
            attribute="part_number",
            expected_value="PROFILE-PN-001",
        )

        device_with_profile = await client.get(kind="TestingDevice", id=device.id, property=True)
        assert device_with_profile.part_number.value == "PROFILE-PN-001"
        assert device_with_profile.part_number.is_from_profile

        profile_to_delete = await client.get(kind="ProfileTestingDevice", id=profile.id)
        with pytest.raises(GraphQLError) as exc_info:
            await profile_to_delete.delete()

        assert "inherits required attribute 'part_number'" in str(exc_info.value)

    async def test_cannot_delete_profile_when_device_inherits_required_relationship(
        self, client: InfrahubClient
    ) -> None:
        manufacturer = await self._create_manufacturer(client=client, name="Manufacturer-constraint-rel")

        profile = await client.create(
            kind="ProfileTestingDevice",
            profile_name="profile-provides-manufacturer",
            profile_priority=1000,
            manufacturer=manufacturer,
        )
        await profile.save()

        device = await client.create(
            kind="TestingDevice", name="device-constraint-rel-1", part_number="MF-PN-CR-1", profiles=[profile]
        )
        await device.save()

        await self.wait_for_relationship_peer(
            client=client,
            kind="TestingDevice",
            node_id=device.id,
            relationship="manufacturer",
            expected_peer_id=manufacturer.id,
        )

        device_with_profile = await client.get(
            kind="TestingDevice", id=device.id, property=True, include=["manufacturer"]
        )
        assert device_with_profile.manufacturer.id == manufacturer.id
        assert device_with_profile.manufacturer.is_from_profile

        profile_to_delete = await client.get(kind="ProfileTestingDevice", id=profile.id)
        with pytest.raises(GraphQLError) as exc_info:
            await profile_to_delete.delete()

        assert "inherits required relationship 'manufacturer'" in str(exc_info.value)

    async def test_can_delete_profile_after_user_sets_required_attribute(self, client: InfrahubClient) -> None:
        manufacturer = await self._create_manufacturer(client=client, name="Manufacturer-user-attr")

        profile = await client.create(
            kind="ProfileTestingDevice",
            profile_name="profile-to-replace-attr",
            profile_priority=1000,
            part_number="PROFILE-PN-002",
        )
        await profile.save()

        device = await client.create(
            kind="TestingDevice", name="device-user-attr-1", manufacturer=manufacturer, profiles=[profile]
        )
        await device.save()

        await self.wait_for_attribute_value(
            client=client,
            kind="TestingDevice",
            node_id=device.id,
            attribute="part_number",
            expected_value="PROFILE-PN-002",
        )

        device_to_update = await client.get(kind="TestingDevice", id=device.id)
        device_to_update.part_number.value = "USER-SET-PN-002"
        await device_to_update.save()

        await self.wait_for_attribute_value(
            client=client,
            kind="TestingDevice",
            node_id=device.id,
            attribute="part_number",
            expected_value="USER-SET-PN-002",
        )

        device_after_update = await client.get(kind="TestingDevice", id=device.id, property=True)
        assert device_after_update.part_number.value == "USER-SET-PN-002"
        assert not device_after_update.part_number.is_from_profile

        profile_to_delete = await client.get(kind="ProfileTestingDevice", id=profile.id)
        await profile_to_delete.delete()

        device_after_delete = await client.get(kind="TestingDevice", id=device.id, property=True)
        assert device_after_delete.part_number.value == "USER-SET-PN-002"
        assert not device_after_delete.part_number.is_from_profile

    async def test_can_delete_profile_after_user_sets_required_relationship(self, client: InfrahubClient) -> None:
        manufacturer_from_profile = await self._create_manufacturer(client=client, name="Manufacturer-from-profile")
        manufacturer_from_user = await self._create_manufacturer(client=client, name="Manufacturer-from-user")

        profile = await client.create(
            kind="ProfileTestingDevice",
            profile_name="profile-to-replace-rel",
            profile_priority=1000,
            manufacturer=manufacturer_from_profile,
        )
        await profile.save()

        device = await client.create(
            kind="TestingDevice", name="device-user-rel-1", part_number="MF-PN-UR-1", profiles=[profile]
        )
        await device.save()

        await self.wait_for_relationship_peer(
            client=client,
            kind="TestingDevice",
            node_id=device.id,
            relationship="manufacturer",
            expected_peer_id=manufacturer_from_profile.id,
        )

        device_to_update = await client.get(kind="TestingDevice", id=device.id, include=["manufacturer"])
        device_to_update.manufacturer = manufacturer_from_user
        await device_to_update.save()

        await self.wait_for_relationship_peer(
            client=client,
            kind="TestingDevice",
            node_id=device.id,
            relationship="manufacturer",
            expected_peer_id=manufacturer_from_user.id,
        )

        device_after_update = await client.get(
            kind="TestingDevice", id=device.id, property=True, include=["manufacturer"]
        )
        assert device_after_update.manufacturer.id == manufacturer_from_user.id
        assert not device_after_update.manufacturer.is_from_profile

        profile_to_delete = await client.get(kind="ProfileTestingDevice", id=profile.id)
        await profile_to_delete.delete()

        device_after_delete = await client.get(
            kind="TestingDevice", id=device.id, property=True, include=["manufacturer"]
        )
        assert device_after_delete.manufacturer.id == manufacturer_from_user.id
        assert not device_after_delete.manufacturer.is_from_profile

    async def test_cannot_remove_node_from_profile_when_inheriting_required_attribute(
        self, client: InfrahubClient
    ) -> None:
        manufacturer = await self._create_manufacturer(client=client, name="Manufacturer-remove-attr")

        profile = await client.create(
            kind="ProfileTestingDevice",
            profile_name="profile-remove-node-attr",
            profile_priority=1000,
            part_number="PROFILE-PN-003",
        )
        await profile.save()

        device = await client.create(
            kind="TestingDevice", name="device-remove-attr-1", manufacturer=manufacturer, profiles=[profile]
        )
        await device.save()

        await self.wait_for_attribute_value(
            client=client,
            kind="TestingDevice",
            node_id=device.id,
            attribute="part_number",
            expected_value="PROFILE-PN-003",
        )

        profile_to_update = await client.get(kind="ProfileTestingDevice", id=profile.id, prefetch_relationships=True)
        await profile_to_update.related_nodes.fetch()
        profile_to_update.related_nodes.remove(device.id)

        with pytest.raises(GraphQLError) as exc_info:
            await profile_to_update.save()

        assert "inherits required attribute 'part_number'" in str(exc_info.value)

    async def test_cannot_remove_node_from_profile_when_inheriting_required_relationship(
        self, client: InfrahubClient
    ) -> None:
        manufacturer = await self._create_manufacturer(client=client, name="Manufacturer-remove-rel")

        profile = await client.create(
            kind="ProfileTestingDevice",
            profile_name="profile-remove-node-rel",
            profile_priority=1000,
            manufacturer=manufacturer,
        )
        await profile.save()

        device = await client.create(
            kind="TestingDevice", name="device-remove-rel-1", part_number="MF-PN-RR-1", profiles=[profile]
        )
        await device.save()

        await self.wait_for_relationship_peer(
            client=client,
            kind="TestingDevice",
            node_id=device.id,
            relationship="manufacturer",
            expected_peer_id=manufacturer.id,
        )

        profile_to_update = await client.get(kind="ProfileTestingDevice", id=profile.id, prefetch_relationships=True)
        await profile_to_update.related_nodes.fetch()
        profile_to_update.related_nodes.remove(device.id)

        with pytest.raises(GraphQLError) as exc_info:
            await profile_to_update.save()

        assert "inherits required relationship 'manufacturer'" in str(exc_info.value)

    async def test_can_remove_node_from_profile_after_user_sets_required_fields(self, client: InfrahubClient) -> None:
        manufacturer_from_profile = await self._create_manufacturer(
            client=client, name="Manufacturer-remove-ok-profile"
        )
        manufacturer_from_user = await self._create_manufacturer(client=client, name="Manufacturer-remove-ok-user")

        profile = await client.create(
            kind="ProfileTestingDevice",
            profile_name="profile-remove-ok",
            profile_priority=1000,
            part_number="PROFILE-PN-004",
            manufacturer=manufacturer_from_profile,
        )
        await profile.save()

        device = await client.create(kind="TestingDevice", name="device-remove-ok-1", profiles=[profile])
        await device.save()

        await self.wait_for_attribute_value(
            client=client,
            kind="TestingDevice",
            node_id=device.id,
            attribute="part_number",
            expected_value="PROFILE-PN-004",
        )

        device_to_update = await client.get(kind="TestingDevice", id=device.id, include=["manufacturer"])
        device_to_update.part_number.value = "USER-SET-PN-004"
        device_to_update.manufacturer = manufacturer_from_user
        await device_to_update.save()

        await self.wait_for_attribute_value(
            client=client,
            kind="TestingDevice",
            node_id=device.id,
            attribute="part_number",
            expected_value="USER-SET-PN-004",
        )

        profile_to_update = await client.get(kind="ProfileTestingDevice", id=profile.id, prefetch_relationships=True)
        await profile_to_update.related_nodes.fetch()
        profile_to_update.related_nodes.remove(device.id)
        await profile_to_update.save()

        device_after_removal = await client.get(
            kind="TestingDevice", id=device.id, property=True, include=["manufacturer"]
        )
        assert device_after_removal.part_number.value == "USER-SET-PN-004"
        assert not device_after_removal.part_number.is_from_profile
        assert device_after_removal.manufacturer.id == manufacturer_from_user.id
        assert not device_after_removal.manufacturer.is_from_profile
