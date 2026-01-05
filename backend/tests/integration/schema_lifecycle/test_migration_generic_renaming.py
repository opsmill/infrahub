import pytest
from infrahub_sdk.client import InfrahubClient

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_no_duplicate_relationships, verify_no_edges_added_after_node_delete
from tests.helpers.schema import load_schema
from tests.integration.schema_lifecycle.shared import TestSchemaLifecycleBase

DEVICE_KIND = "TestingDevice"
DEVICE_ROLE_KIND = "TestingDeviceRole"


class TestSchemaLifecycleGenericRenaming(TestSchemaLifecycleBase):
    @pytest.fixture(scope="class")
    def schema_role_generic(self) -> GenericSchema:
        return GenericSchema(
            name="DeviceRole",
            namespace="Testing",
            attributes=[AttributeSchema(name="role", kind="Text", unique=True)],
        )

    @pytest.fixture(scope="class")
    def schema_device(self) -> NodeSchema:
        return NodeSchema(
            name="Device",
            namespace="Testing",
            inherit_from=[DEVICE_ROLE_KIND],
            attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
        )

    @pytest.fixture(scope="class")
    async def schema_step_01(self, schema_role_generic: GenericSchema, schema_device: NodeSchema) -> SchemaRoot:
        return SchemaRoot(version="1.0", generics=[schema_role_generic], nodes=[schema_device])

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self, db: InfrahubDatabase, initialize_registry, schema_step_01: SchemaRoot
    ) -> dict[str, str]:
        await load_schema(db=db, schema=schema_step_01, update_db=True)

        first_device = await Node.init(schema=DEVICE_KIND, db=db)
        await first_device.new(db=db, name="Test Device 01", role="Provider Edge")
        await first_device.save(db=db)

        second_device = await Node.init(schema=DEVICE_KIND, db=db)
        await second_device.new(db=db, name="Test Device 02", role="Provider Edge")
        await second_device.save(db=db)

        deleted_device = await Node.init(schema=DEVICE_KIND, db=db)
        await deleted_device.new(db=db, name="Test Device Deleted", role="Provider Edge")
        await deleted_device.save(db=db)
        await deleted_device.delete(db=db)

        objs = {"first_device": first_device.id, "second_device": second_device.id}

        return objs

    async def test_step01_baseline(self, db: InfrahubDatabase, initial_dataset: dict[str, str]) -> None:
        devices = await registry.manager.query(db=db, schema=DEVICE_KIND)
        assert len(devices) == 2

    async def test_step02_load_schema_update(self, db: InfrahubDatabase, client: InfrahubClient) -> None:
        role_schema = registry.schema.get(name=DEVICE_ROLE_KIND, duplicate=False).model_dump()
        device_schema = registry.schema.get(name=DEVICE_KIND, duplicate=False).model_dump()

        assert role_schema["id"]
        assert device_schema["id"]

        # Keeping the same ID is important
        role_schema["namespace"] = "Foo"
        device_schema["inherit_from"] = ["FooDeviceRole"]

        response = await client.schema.load(
            schemas=[{"version": "1.0", "generics": [role_schema]}, {"version": "1.0", "nodes": [device_schema]}]
        )
        assert not response.errors

    async def test_step03_get_devices(self, db: InfrahubDatabase) -> None:
        devices = await registry.manager.query(db=db, schema=DEVICE_KIND)
        assert len(devices) == 2

    async def test_step04_get_devices_via_graphql(self, client: InfrahubClient) -> None:
        devices = await client.all(kind=DEVICE_KIND)
        assert len(devices) == 2

    async def test_final_validate(self, db: InfrahubDatabase) -> None:
        await verify_no_duplicate_relationships(db=db)
        await verify_no_edges_added_after_node_delete(db=db)
