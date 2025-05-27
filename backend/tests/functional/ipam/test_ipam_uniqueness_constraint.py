import copy

import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.exceptions import GraphQLError

from infrahub.core.branch.models import Branch
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from tests.constants import TestKind
from tests.helpers.schema import load_schema
from tests.helpers.schema.device import DEVICE
from tests.helpers.test_app import TestInfrahubApp


class TestUniqueIPHost(TestInfrahubApp):
    @pytest.fixture(scope="class", autouse=True)
    def schema(self, default_branch: Branch, register_internal_schema: SchemaBranch) -> SchemaRoot:
        device_with_ip = copy.deepcopy(DEVICE)
        device_with_ip.inherit_from = []
        device_with_ip.generate_template = False
        device_with_ip.attributes.append(
            AttributeSchema(name="primary_address", kind="IPHost", optional=False, unique=True)
        )
        return SchemaRoot(nodes=[device_with_ip])

    @pytest.fixture(scope="class")
    async def data(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        default_branch: Branch,
        schema: SchemaRoot,
    ) -> dict[str, Node]:
        await load_schema(db, schema=schema, update_db=True)

        device = await Node.init(db=db, schema=TestKind.DEVICE)
        await device.new(
            db=db,
            name="Foo",
            manufacturer="Foo Inc.",
            weight=10,
            airflow="Front to rear",
            primary_address="192.168.1.1/24",
        )
        await device.save(db=db)

        return {"device": device}

    async def test_create_devices(self, client: InfrahubClient, data: dict[str, Node]) -> None:
        device_1 = await client.create(
            TestKind.DEVICE,
            name="Bar",
            manufacturer="Bar Inc.",
            weight=10,
            airflow="Front to rear",
            primary_address="192.168.1.2/24",
        )
        await device_1.save()

        devices = await client.all(kind=TestKind.DEVICE)
        assert len(devices) == 2

        device_2 = await client.create(
            TestKind.DEVICE,
            name="Baz",
            manufacturer="Baz Inc.",
            weight=10,
            airflow="Front to rear",
            primary_address="192.168.1.2/255.255.255.0",
        )
        with pytest.raises(GraphQLError) as exc:
            await device_2.save()
        assert exc.value.errors[0]["message"] == "Violates uniqueness constraint 'primary_address'"

        devices = await client.all(kind=TestKind.DEVICE)
        assert len(devices) == 2
