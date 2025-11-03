from typing import Any

import pytest
from attr import dataclass
from infrahub_sdk.branch import BranchData
from infrahub_sdk.client import InfrahubClient
from infrahub_sdk.exceptions import BranchNotFoundError, NodeNotFoundError
from infrahub_sdk.node.node import InfrahubNode

from infrahub.core.branch import Branch
from tests.constants import TestKind
from tests.helpers.schema import DEVICE_SCHEMA
from tests.helpers.test_app import TestInfrahubApp

BRANCH_NAMES = ["main", "branch2"]


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
