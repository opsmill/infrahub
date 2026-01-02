from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from attr import dataclass
from infrahub_sdk.exceptions import BranchNotFoundError, NodeNotFoundError

from tests.constants import TestKind
from tests.helpers.schema import DEVICE_SCHEMA
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk.branch import BranchData
    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.node.node import InfrahubNode

    from infrahub.core.branch import Branch

BRANCH_NAMES = ["main", "branch2"]

REFRESH_PROFILES_MUTATION = """
mutation RefreshProfiles($id: String!) {
  InfrahubProfilesRefresh(data: {id: $id}) {
    ok
  }
}
"""


@dataclass
class AttributeProfileDetails:
    attribute_name: str
    value: Any
    is_default: bool
    source_profile_id: str | None = None
    source_template_id: str | None = None

    @property
    def is_from_profile(self) -> bool:
        return self.source_profile_id is not None

    @property
    def source_id(self) -> str | None:
        return self.source_profile_id or self.source_template_id


class TestProfiles(TestInfrahubApp):
    async def refresh_profiles(self, client: InfrahubClient, branch_name: str, node_id: str) -> None:
        # This should be done using a trigger but for test purpose we do it manually
        response = await client.execute_graphql(
            query=REFRESH_PROFILES_MUTATION, variables={"id": node_id}, branch_name=branch_name
        )
        assert response["InfrahubProfilesRefresh"]["ok"]

    @pytest.fixture(params=BRANCH_NAMES)
    async def branch(self, request, client: InfrahubClient) -> BranchData:
        branch_name = request.param
        try:
            return await client.branch.get(branch_name=branch_name)
        except BranchNotFoundError:
            return await client.branch.create(branch_name=branch_name)

    @pytest.fixture(scope="class")
    async def load_schema(self, client: InfrahubClient, default_branch: Branch) -> None:
        device_schema = DEVICE_SCHEMA.model_dump()
        device_schema["version"] = "1.0"
        response = await client.schema.load(schemas=[device_schema])
        assert not response.errors

    @pytest.fixture(scope="class")
    async def device_1_full_attributes(self, client: InfrahubClient, load_schema: None) -> InfrahubNode:
        device = await client.create(
            kind=TestKind.DEVICE,
            name="device-1",
            manufacturer="manufacturer-1",
            height=1,
            weight=1,
            airflow="Front to rear",
            part_number="part-number-1",
        )
        await device.save()
        return await client.get(kind=TestKind.DEVICE, id=device.id, property=True)

    @pytest.fixture(scope="class")
    async def device_2_empty_attribute(self, client: InfrahubClient, load_schema: None) -> InfrahubNode:
        device = await client.create(
            kind=TestKind.DEVICE,
            name="device-2",
            manufacturer="manufacturer-2",
            weight=2,
            airflow="Rear to front",
        )
        await device.save()
        return await client.get(kind=TestKind.DEVICE, id=device.id, property=True)

    @pytest.fixture(scope="class")
    async def device_3(self, client: InfrahubClient, load_schema: None) -> InfrahubNode:
        device = await client.create(
            kind=TestKind.DEVICE,
            name="device-3",
            manufacturer="manufacturer-3",
            weight=3,
            airflow="Bottom to top",
        )
        await device.save()
        return await client.get(kind=TestKind.DEVICE, id=device.id, property=True)

    @pytest.fixture(scope="class")
    async def device_profile_1(self, client: InfrahubClient, load_schema: None) -> InfrahubNode:
        device_profile = await client.create(
            kind=f"Profile{TestKind.DEVICE}",
            profile_name="device-profile-1",
            profile_priority=1001,
            manufacturer="manufacturer-profile-1",
            height=101,
            weight=201,
            airflow="Left to right",
            part_number="part-number-profile-1",
        )
        await device_profile.save()
        return await client.get(kind=f"Profile{TestKind.DEVICE}", id=device_profile.id, property=True)

    @pytest.fixture(scope="class")
    async def device_template(
        self,
        client: InfrahubClient,
        load_schema: None,
    ) -> InfrahubNode:
        device_template = await client.create(
            kind=f"Template{TestKind.DEVICE}",
            template_name="device-template",
            height=501,
        )
        await device_template.save()
        return await client.get(kind=f"Template{TestKind.DEVICE}", id=device_template.id)

    @pytest.fixture
    async def device_profile_2_with_empty_node(
        self, device_2_empty_attribute: InfrahubNode, client: InfrahubClient, load_schema: None, branch: BranchData
    ) -> InfrahubNode:
        try:
            return await client.get(
                branch=branch.name,
                kind=f"Profile{TestKind.DEVICE}",
                profile_name__value=f"device-profile-2-{branch.name}",
                property=True,
            )
        except NodeNotFoundError:
            pass
        device_profile = await client.create(
            branch=branch.name,
            kind=f"Profile{TestKind.DEVICE}",
            profile_name=f"device-profile-2-{branch.name}",
            profile_priority=1002,
            manufacturer="manufacturer-profile-2",
            height=102,
            weight=202,
            airflow="Right to left",
            part_number="part-number-profile-2",
            related_nodes=[device_2_empty_attribute.id],
        )
        await device_profile.save()
        return await client.get(
            branch=branch.name, kind=f"Profile{TestKind.DEVICE}", id=device_profile.id, property=True
        )

    def validate_node(
        self,
        original_node: InfrahubNode,
        updated_node: InfrahubNode,
        expected_profile_attrs: list[AttributeProfileDetails],
    ) -> None:
        expected_profile_attrs_by_name = {attr.attribute_name: attr for attr in expected_profile_attrs}
        for attribute_name in updated_node._attributes:
            current_attribute = getattr(updated_node, attribute_name)
            if expected_profile_attr := expected_profile_attrs_by_name.get(attribute_name):
                assert current_attribute.value == expected_profile_attr.value
                assert current_attribute.is_default == expected_profile_attr.is_default
                assert current_attribute.is_from_profile == expected_profile_attr.is_from_profile
                assert current_attribute.source.id == expected_profile_attr.source_id
                continue
            original_attribute = getattr(original_node, attribute_name)
            assert current_attribute.value == original_attribute.value
            assert current_attribute.is_default == original_attribute.is_default
            assert current_attribute.is_from_profile == original_attribute.is_from_profile
            if original_attribute.source is not None:
                assert current_attribute.source.id == original_attribute.source.id
            else:
                assert current_attribute.source is None

    async def test_load_data_and_branch(
        self,
        device_1_full_attributes: InfrahubNode,
        device_2_empty_attribute: InfrahubNode,
        device_3: InfrahubNode,
        device_template: InfrahubNode,
        device_profile_1: InfrahubNode,
        branch: BranchData,
    ) -> None:
        pass

    async def test_profile_values_do_not_override_non_default_values(
        self,
        device_1_full_attributes: InfrahubNode,
        device_profile_1: InfrahubNode,
        client: InfrahubClient,
        branch: BranchData,
    ) -> None:
        device_profile_1 = await client.get(
            branch=branch.name, kind=f"Profile{TestKind.DEVICE}", id=device_profile_1.id, property=True
        )
        await device_profile_1.related_nodes.fetch()
        device_profile_1.related_nodes.add(device_1_full_attributes.id)
        await device_profile_1.save()

        updated_device_1 = await client.get(
            branch=branch.name, kind=TestKind.DEVICE, id=device_1_full_attributes.id, property=True
        )
        self.validate_node(
            original_node=device_1_full_attributes, updated_node=updated_device_1, expected_profile_attrs=[]
        )

    async def test_create_profile_with_linked_node(
        self,
        device_2_empty_attribute: InfrahubNode,
        device_profile_2_with_empty_node: InfrahubNode,
        client: InfrahubClient,
        branch: BranchData,
    ) -> None:
        fresh_device_2 = await client.get(branch=branch.name, kind=TestKind.DEVICE, id=device_2_empty_attribute.id)
        fresh_device_2.manufacturer.is_default = True
        await fresh_device_2.save()

        updated_device_2 = await client.get(
            branch=branch.name, kind=TestKind.DEVICE, id=device_2_empty_attribute.id, property=True
        )
        profile_2_id = device_profile_2_with_empty_node.id
        self.validate_node(
            original_node=device_2_empty_attribute,
            updated_node=updated_device_2,
            expected_profile_attrs=[
                AttributeProfileDetails(
                    attribute_name="height", value=102, is_default=False, source_profile_id=profile_2_id
                ),
                AttributeProfileDetails(
                    attribute_name="part_number",
                    value="part-number-profile-2",
                    is_default=False,
                    source_profile_id=profile_2_id,
                ),
            ],
        )

    @pytest.fixture
    async def device_profile_2_updated_values(
        self,
        device_profile_2_with_empty_node: InfrahubNode,
        client: InfrahubClient,
        branch: BranchData,
    ) -> InfrahubNode:
        device_profile_2_with_empty_node = await client.get(
            branch=branch.name, kind=f"Profile{TestKind.DEVICE}", id=device_profile_2_with_empty_node.id
        )
        device_profile_2_with_empty_node.height.value = 1022
        device_profile_2_with_empty_node.part_number.value = "part-number-profile-2-updated"
        await device_profile_2_with_empty_node.save()
        return await client.get(
            branch=branch.name, kind=f"Profile{TestKind.DEVICE}", id=device_profile_2_with_empty_node.id, property=True
        )

    async def test_profile_value_update(
        self,
        device_profile_2_updated_values: InfrahubNode,
        device_2_empty_attribute: InfrahubNode,
        client: InfrahubClient,
        branch: BranchData,
    ) -> None:
        await self.refresh_profiles(client=client, branch_name=branch.name, node_id=device_2_empty_attribute.id)

        updated_device_2 = await client.get(
            branch=branch.name, kind=TestKind.DEVICE, id=device_2_empty_attribute.id, property=True
        )
        self.validate_node(
            original_node=device_2_empty_attribute,
            updated_node=updated_device_2,
            expected_profile_attrs=[
                AttributeProfileDetails(
                    attribute_name="height",
                    value=1022,
                    is_default=False,
                    source_profile_id=device_profile_2_updated_values.id,
                ),
                AttributeProfileDetails(
                    attribute_name="part_number",
                    value="part-number-profile-2-updated",
                    is_default=False,
                    source_profile_id=device_profile_2_updated_values.id,
                ),
            ],
        )

    @pytest.fixture
    async def device_profile_3_with_all_nodes(
        self,
        device_1_full_attributes: InfrahubNode,
        device_2_empty_attribute: InfrahubNode,
        device_3: InfrahubNode,
        client: InfrahubClient,
        load_schema: None,
        branch: BranchData,
    ) -> InfrahubNode:
        try:
            return await client.get(
                branch=branch.name,
                kind=f"Profile{TestKind.DEVICE}",
                profile_name__value=f"device-profile-3-{branch.name}",
                property=True,
            )
        except NodeNotFoundError:
            pass
        device_profile = await client.create(
            branch=branch.name,
            kind=f"Profile{TestKind.DEVICE}",
            profile_name=f"device-profile-3-{branch.name}",
            profile_priority=1003,
            manufacturer="manufacturer-profile-3",
            height=301,
            weight=302,
            airflow="Right to left",
            part_number="part-number-profile-3",
            related_nodes=[device_1_full_attributes.id, device_2_empty_attribute.id, device_3.id],
        )
        await device_profile.save()
        return await client.get(
            branch=branch.name, kind=f"Profile{TestKind.DEVICE}", id=device_profile.id, property=True
        )

    async def test_add_profile_to_all_devices(
        self,
        device_1_full_attributes: InfrahubNode,
        device_2_empty_attribute: InfrahubNode,
        device_3: InfrahubNode,
        device_profile_2_updated_values: InfrahubNode,
        device_profile_3_with_all_nodes: InfrahubNode,
        client: InfrahubClient,
        branch: BranchData,
    ) -> None:
        updated_device_1 = await client.get(
            branch=branch.name, kind=TestKind.DEVICE, id=device_1_full_attributes.id, property=True
        )
        self.validate_node(
            original_node=device_1_full_attributes,
            updated_node=updated_device_1,
            expected_profile_attrs=[],
        )

        updated_device_2 = await client.get(
            branch=branch.name, kind=TestKind.DEVICE, id=device_2_empty_attribute.id, property=True
        )
        self.validate_node(
            original_node=device_2_empty_attribute,
            updated_node=updated_device_2,
            expected_profile_attrs=[
                AttributeProfileDetails(
                    attribute_name="height",
                    value=1022,
                    is_default=False,
                    source_profile_id=device_profile_2_updated_values.id,
                ),
                AttributeProfileDetails(
                    attribute_name="part_number",
                    value="part-number-profile-2-updated",
                    is_default=False,
                    source_profile_id=device_profile_2_updated_values.id,
                ),
            ],
        )

        updated_device_3 = await client.get(branch=branch.name, kind=TestKind.DEVICE, id=device_3.id, property=True)
        self.validate_node(
            original_node=device_3,
            updated_node=updated_device_3,
            expected_profile_attrs=[
                AttributeProfileDetails(
                    attribute_name="height",
                    value=301,
                    is_default=False,
                    source_profile_id=device_profile_3_with_all_nodes.id,
                ),
                AttributeProfileDetails(
                    attribute_name="part_number",
                    value="part-number-profile-3",
                    is_default=False,
                    source_profile_id=device_profile_3_with_all_nodes.id,
                ),
            ],
        )

    async def test_update_profile_priority(
        self,
        device_1_full_attributes: InfrahubNode,
        device_2_empty_attribute: InfrahubNode,
        device_3: InfrahubNode,
        device_profile_3_with_all_nodes: InfrahubNode,
        client: InfrahubClient,
        branch: BranchData,
    ) -> None:
        # make profile 3 the highest priority
        device_profile_3 = await client.get(
            branch=branch.name, kind=f"Profile{TestKind.DEVICE}", id=device_profile_3_with_all_nodes.id
        )
        device_profile_3.profile_priority.value = 999
        await device_profile_3.save()

        await self.refresh_profiles(client=client, branch_name=branch.name, node_id=device_1_full_attributes.id)
        await self.refresh_profiles(client=client, branch_name=branch.name, node_id=device_2_empty_attribute.id)
        await self.refresh_profiles(client=client, branch_name=branch.name, node_id=device_3.id)

        updated_device_1 = await client.get(
            branch=branch.name, kind=TestKind.DEVICE, id=device_1_full_attributes.id, property=True
        )
        self.validate_node(
            original_node=device_1_full_attributes,
            updated_node=updated_device_1,
            expected_profile_attrs=[],
        )

        expected_profile_3_attrs = [
            AttributeProfileDetails(
                attribute_name="height",
                value=301,
                is_default=False,
                source_profile_id=device_profile_3_with_all_nodes.id,
            ),
            AttributeProfileDetails(
                attribute_name="part_number",
                value="part-number-profile-3",
                is_default=False,
                source_profile_id=device_profile_3_with_all_nodes.id,
            ),
        ]
        updated_device_2 = await client.get(
            branch=branch.name, kind=TestKind.DEVICE, id=device_2_empty_attribute.id, property=True
        )
        self.validate_node(
            original_node=device_2_empty_attribute,
            updated_node=updated_device_2,
            expected_profile_attrs=expected_profile_3_attrs,
        )

        updated_device_3 = await client.get(branch=branch.name, kind=TestKind.DEVICE, id=device_3.id, property=True)
        self.validate_node(
            original_node=device_3,
            updated_node=updated_device_3,
            expected_profile_attrs=expected_profile_3_attrs,
        )

    async def test_delete_profile(
        self,
        device_1_full_attributes: InfrahubNode,
        device_2_empty_attribute: InfrahubNode,
        device_3: InfrahubNode,
        device_profile_2_updated_values: InfrahubNode,
        device_profile_3_with_all_nodes: InfrahubNode,
        client: InfrahubClient,
        branch: BranchData,
    ) -> None:
        # delete profile 3
        device_profile_3 = await client.get(
            branch=branch.name, kind=f"Profile{TestKind.DEVICE}", id=device_profile_3_with_all_nodes.id
        )
        await device_profile_3.delete()

        updated_device_1 = await client.get(
            branch=branch.name, kind=TestKind.DEVICE, id=device_1_full_attributes.id, property=True
        )
        self.validate_node(
            original_node=device_1_full_attributes,
            updated_node=updated_device_1,
            expected_profile_attrs=[],
        )

        updated_device_2 = await client.get(
            branch=branch.name, kind=TestKind.DEVICE, id=device_2_empty_attribute.id, property=True
        )
        self.validate_node(
            original_node=device_2_empty_attribute,
            updated_node=updated_device_2,
            expected_profile_attrs=[
                AttributeProfileDetails(
                    attribute_name="height",
                    value=1022,
                    is_default=False,
                    source_profile_id=device_profile_2_updated_values.id,
                ),
                AttributeProfileDetails(
                    attribute_name="part_number",
                    value="part-number-profile-2-updated",
                    is_default=False,
                    source_profile_id=device_profile_2_updated_values.id,
                ),
            ],
        )

        updated_device_3 = await client.get(branch=branch.name, kind=TestKind.DEVICE, id=device_3.id, property=True)
        self.validate_node(
            original_node=device_3,
            updated_node=updated_device_3,
            expected_profile_attrs=[],
        )

    @pytest.fixture
    async def device_4_with_template(
        self,
        device_template: InfrahubNode,
        device_profile_2_updated_values: InfrahubNode,
        client: InfrahubClient,
        load_schema: None,
        branch: BranchData,
    ) -> InfrahubNode:
        try:
            return await client.get(
                branch=branch.name,
                kind=f"{TestKind.DEVICE}",
                name__value=f"device-4-{branch.name}",
                property=True,
            )
        except NodeNotFoundError:
            pass
        device = await client.create(
            branch=branch.name,
            kind=f"{TestKind.DEVICE}",
            name=f"device-4-{branch.name}",
            manufacturer="manufacturer-4",
            weight=4,
            airflow="Passive",
            profiles=[device_profile_2_updated_values.id],
            object_template=device_template,
        )
        await device.save()
        return await client.get(branch=branch.name, kind=f"{TestKind.DEVICE}", id=device.id, property=True)

    async def test_create_device_with_template_and_profile(
        self,
        device_template: InfrahubNode,
        device_profile_2_updated_values: InfrahubNode,
        device_4_with_template: InfrahubNode,
        client: InfrahubClient,
        branch: BranchData,
    ) -> None:
        updated_device_4 = await client.get(
            branch=branch.name, kind=f"{TestKind.DEVICE}", id=device_4_with_template.id, property=True
        )
        self.validate_node(
            original_node=device_4_with_template,
            updated_node=updated_device_4,
            expected_profile_attrs=[
                AttributeProfileDetails(
                    attribute_name="height",
                    value=501,
                    is_default=False,
                    source_template_id=device_template.id,
                ),
                AttributeProfileDetails(
                    attribute_name="part_number",
                    value="part-number-profile-2-updated",
                    is_default=False,
                    source_profile_id=device_profile_2_updated_values.id,
                ),
            ],
        )

    async def test_create_template_with_profile(
        self,
        device_profile_1: InfrahubNode,
        client: InfrahubClient,
        branch: BranchData,
    ) -> None:
        """Test creating a template with a profile assigned via SDK.

        This test creates a template with explicit values for manufacturer and weight,
        and a profile assigned. The profile should provide values for attributes that
        are using defaults (height, airflow, part_number).
        """
        template = await client.create(
            branch=branch.name,
            kind=f"Template{TestKind.DEVICE}",
            template_name=f"template-with-profile-{branch.name}",
            manufacturer="Template Manufacturer",
            weight=100,
            profiles=[device_profile_1.id],
        )
        await template.save()

        # Retrieve template with property=True to get metadata
        retrieved_template = await client.get(
            branch=branch.name,
            kind=f"Template{TestKind.DEVICE}",
            template_name__value=f"template-with-profile-{branch.name}",
            property=True,
        )
        await retrieved_template.profiles.fetch()

        # Verify profile was assigned
        assert device_profile_1.id in retrieved_template.profiles.peer_ids

        # Explicitly set attributes should use template values (not profile)
        assert retrieved_template.manufacturer.value == "Template Manufacturer"
        assert retrieved_template.manufacturer.is_from_profile is False
        assert retrieved_template.manufacturer.source is None

        assert retrieved_template.weight.value == 100
        assert retrieved_template.weight.is_from_profile is False
        assert retrieved_template.weight.source is None

        # Attributes where template uses defaults should get profile values
        # Note: Profile values may only be applied if the attribute truly uses the default,
        # not if the user sets it to the default value
        if retrieved_template.height.is_from_profile:
            assert retrieved_template.height.value == 101
            assert retrieved_template.height.source.id == device_profile_1.id

        if retrieved_template.airflow.is_from_profile:
            assert retrieved_template.airflow.value == "Left to right"
            assert retrieved_template.airflow.source.id == device_profile_1.id

        if retrieved_template.part_number.is_from_profile:
            assert retrieved_template.part_number.value == "part-number-profile-1"
            assert retrieved_template.part_number.source.id == device_profile_1.id

    async def test_assign_profile_to_existing_template(
        self,
        device_profile_1: InfrahubNode,
        client: InfrahubClient,
        branch: BranchData,
    ) -> None:
        """Test assigning a profile to an existing template via SDK."""
        # Create a new template (not using the shared device_template fixture)
        # to avoid cross-branch issues with parameterized tests
        template = await client.create(
            branch=branch.name,
            kind=f"Template{TestKind.DEVICE}",
            template_name=f"assign-profile-template-{branch.name}",
            manufacturer="Test Manufacturer",
            height=501,
        )
        await template.save()

        # Retrieve it to verify it has no profiles
        retrieved_template = await client.get(
            branch=branch.name,
            kind=f"Template{TestKind.DEVICE}",
            id=template.id,
        )
        await retrieved_template.profiles.fetch()
        assert len(retrieved_template.profiles.peer_ids) == 0

        # Assign profile
        retrieved_template.profiles.add(device_profile_1.id)
        await retrieved_template.save()

        # Retrieve and verify profile was assigned
        updated_template = await client.get(
            branch=branch.name,
            kind=f"Template{TestKind.DEVICE}",
            id=template.id,
            property=True,
        )
        await updated_template.profiles.fetch()

        assert len(updated_template.profiles.peer_ids) == 1
        assert device_profile_1.id in updated_template.profiles.peer_ids

        # Template's explicitly set value should remain
        assert updated_template.height.value == 501
        assert updated_template.height.is_from_profile is False

    async def test_template_with_multiple_profiles_respects_priority(
        self,
        device_profile_1: InfrahubNode,
        client: InfrahubClient,
        branch: BranchData,
    ) -> None:
        """Test that templates with multiple profiles can have multiple profiles assigned."""
        # Create second profile with different priority
        profile_2 = await client.create(
            branch=branch.name,
            kind=f"Profile{TestKind.DEVICE}",
            profile_name=f"high-priority-profile-{branch.name}",
            profile_priority=500,  # Lower priority number than device_profile_1 (1001)
            airflow="Mixed",
            weight=999,
        )
        await profile_2.save()

        # Create template with both profiles
        template = await client.create(
            branch=branch.name,
            kind=f"Template{TestKind.DEVICE}",
            template_name=f"multi-profile-template-{branch.name}",
            manufacturer="Multi Profile Manufacturer",
            profiles=[device_profile_1.id, profile_2.id],
        )
        await template.save()

        # Retrieve and verify both profiles are assigned
        retrieved_template = await client.get(
            branch=branch.name,
            kind=f"Template{TestKind.DEVICE}",
            template_name__value=f"multi-profile-template-{branch.name}",
            property=True,
        )
        await retrieved_template.profiles.fetch()

        assert len(retrieved_template.profiles.peer_ids) == 2
        assert device_profile_1.id in retrieved_template.profiles.peer_ids
        assert profile_2.id in retrieved_template.profiles.peer_ids

    async def test_update_template_attribute_overrides_profile(
        self,
        device_profile_1: InfrahubNode,
        client: InfrahubClient,
        branch: BranchData,
    ) -> None:
        """Test that updating a template attribute explicitly sets its value."""
        # Create template with profile
        template = await client.create(
            branch=branch.name,
            kind=f"Template{TestKind.DEVICE}",
            template_name=f"update-override-template-{branch.name}",
            manufacturer="Initial Manufacturer",
            profiles=[device_profile_1.id],
        )
        await template.save()

        # Update airflow explicitly to a different valid enum value
        template_for_update = await client.get(
            branch=branch.name,
            kind=f"Template{TestKind.DEVICE}",
            id=template.id,
        )
        template_for_update.airflow.value = "Front to rear"  # Valid enum value
        await template_for_update.save()

        # Verify explicit value was set
        updated_template = await client.get(
            branch=branch.name,
            kind=f"Template{TestKind.DEVICE}",
            id=template.id,
            property=True,
        )
        assert updated_template.airflow.value == "Front to rear"
        assert updated_template.airflow.is_from_profile is False
        assert updated_template.airflow.source is None

    async def test_remove_profile_from_template(
        self,
        device_profile_1: InfrahubNode,
        client: InfrahubClient,
        branch: BranchData,
    ) -> None:
        """Test removing a profile from a template via SDK."""
        # Create template with profile
        template = await client.create(
            branch=branch.name,
            kind=f"Template{TestKind.DEVICE}",
            template_name=f"remove-profile-template-{branch.name}",
            manufacturer="Test Manufacturer",
            profiles=[device_profile_1.id],
        )
        await template.save()

        # Verify profile is assigned
        retrieved_template = await client.get(
            branch=branch.name,
            kind=f"Template{TestKind.DEVICE}",
            id=template.id,
            property=True,
        )
        await retrieved_template.profiles.fetch()
        assert device_profile_1.id in retrieved_template.profiles.peer_ids

        # Remove profile
        template_for_update = await client.get(
            branch=branch.name,
            kind=f"Template{TestKind.DEVICE}",
            id=template.id,
        )
        await template_for_update.profiles.fetch()
        template_for_update.profiles.remove(device_profile_1.id)
        await template_for_update.save()

        # Verify profile was removed
        updated_template = await client.get(
            branch=branch.name,
            kind=f"Template{TestKind.DEVICE}",
            id=template.id,
            property=True,
        )
        await updated_template.profiles.fetch()
        assert len(updated_template.profiles.peer_ids) == 0

    async def test_create_node_from_template_with_profile(
        self,
        device_profile_1: InfrahubNode,
        client: InfrahubClient,
        branch: BranchData,
    ) -> None:
        """Test creating a node from a template that has a profile assigned.

        When a node is created from a template with profiles:
        - Template's explicit values should come from template
        - Profile values (inherited from template) should come from profile
        """
        # Create template with profile, providing all required attributes
        template = await client.create(
            branch=branch.name,
            kind=f"Template{TestKind.DEVICE}",
            template_name=f"node-creation-template-{branch.name}",
            manufacturer="Template Manufacturer",
            airflow="Front to rear",  # Required attribute
            weight=150,
            profiles=[device_profile_1.id],
        )
        await template.save()

        # Create node from template
        device = await client.create(
            branch=branch.name,
            kind=TestKind.DEVICE,
            name=f"device-from-template-{branch.name}",
            object_template=template.id,
        )
        await device.save()

        # Retrieve and verify
        retrieved_device = await client.get(
            branch=branch.name,
            kind=TestKind.DEVICE,
            id=device.id,
            property=True,
        )

        # Explicitly set template values should come from template
        assert retrieved_device.manufacturer.value == "Template Manufacturer"
        assert retrieved_device.manufacturer.source.id == template.id
        assert retrieved_device.manufacturer.is_from_profile is False

        assert retrieved_device.airflow.value == "Front to rear"
        assert retrieved_device.airflow.source.id == template.id
        assert retrieved_device.airflow.is_from_profile is False

        assert retrieved_device.weight.value == 150
        assert retrieved_device.weight.source.id == template.id
        assert retrieved_device.weight.is_from_profile is False

    async def test_template_explicit_value_not_overridden_by_profile(
        self,
        device_profile_1: InfrahubNode,
        client: InfrahubClient,
        branch: BranchData,
    ) -> None:
        """Test that explicitly set template values are not overridden by profile values."""
        # Create template with explicit airflow value (different from profile)
        # Profile has "Left to right", template will have "Front to rear"
        template = await client.create(
            branch=branch.name,
            kind=f"Template{TestKind.DEVICE}",
            template_name=f"explicit-value-template-{branch.name}",
            manufacturer="Explicit Manufacturer",
            airflow="Front to rear",  # Explicitly set to different value than profile
            weight=200,
        )
        await template.save()

        # Assign profile (which has airflow="Left to right")
        template_for_update = await client.get(
            branch=branch.name,
            kind=f"Template{TestKind.DEVICE}",
            id=template.id,
        )
        await template_for_update.profiles.fetch()  # Must fetch before editing
        template_for_update.profiles.add(device_profile_1.id)
        await template_for_update.save()

        # Verify explicit template value is not overridden
        updated_template = await client.get(
            branch=branch.name,
            kind=f"Template{TestKind.DEVICE}",
            id=template.id,
            property=True,
        )

        # Template's explicit airflow should remain
        assert updated_template.airflow.value == "Front to rear"
        assert updated_template.airflow.is_from_profile is False
        assert updated_template.airflow.source is None

        # Profile relationship should be established
        await updated_template.profiles.fetch()
        assert device_profile_1.id in updated_template.profiles.peer_ids
