import pytest
from infrahub_sdk.client import InfrahubClient
from infrahub_sdk.node.node import InfrahubNode

from infrahub.core.branch import Branch
from tests.constants import TestKind
from tests.helpers.schema import DEVICE_SCHEMA
from tests.helpers.test_app import TestInfrahubApp


class TestProfiles(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def load_schema(self, client: InfrahubClient, default_branch: Branch) -> None:
        device_schema = DEVICE_SCHEMA.model_dump()
        device_schema["version"] = "1.0"
        response = await client.schema.load(schemas=[device_schema])
        assert not response.errors

    @pytest.fixture(scope="class")
    async def device_1(self, client: InfrahubClient, load_schema: None) -> InfrahubNode:
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
        return device

    @pytest.fixture(scope="class")
    async def device_profile_1(self, client: InfrahubClient, load_schema: None) -> InfrahubNode:
        device_profile = await client.create(
            kind=f"Profile{TestKind.DEVICE}",
            profile_name="device-profile-1",
            profile_priority=1000,
            manufacturer="manufacturer-profile-1",
            height=101,
            weight=201,
            airflow="Left to right",
            part_number="part-number-profile-1",
        )
        await device_profile.save()
        return device_profile

    async def test_profile_values_do_not_override_non_default_values(
        self,
        device_1: InfrahubNode,
        device_profile_1: InfrahubNode,
        client: InfrahubClient,
    ):
        await device_profile_1.related_nodes.fetch()
        device_profile_1.related_nodes.add(device_1.id)
        await device_profile_1.save()

        updated_device_1 = await client.get(kind=TestKind.DEVICE, id=device_1.id, property=True)
        assert updated_device_1.manufacturer.value == "manufacturer-1"
        assert updated_device_1.manufacturer.is_default is False
        assert updated_device_1.manufacturer.is_from_profile is False
        assert updated_device_1.manufacturer.source is None

        assert updated_device_1.height.value == 1
        assert updated_device_1.height.is_default is False
        assert updated_device_1.height.is_from_profile is False
        assert updated_device_1.height.source is None

        assert updated_device_1.weight.value == 1
        assert updated_device_1.weight.is_default is False
        assert updated_device_1.weight.is_from_profile is False
        assert updated_device_1.weight.source is None

        assert updated_device_1.airflow.value == "Front to rear"
        assert updated_device_1.airflow.is_default is False
        assert updated_device_1.airflow.is_from_profile is False
        assert updated_device_1.airflow.source is None

        assert updated_device_1.part_number.value == "part-number-1"
        assert updated_device_1.part_number.is_default is False
        assert updated_device_1.part_number.is_from_profile is False
        assert updated_device_1.part_number.source is None


# test setting attribute value back to default picks up profile value
# test profile create with linked node
# test profile update
# test profile delete
