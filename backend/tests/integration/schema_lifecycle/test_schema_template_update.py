from typing import Any

import pytest
from infrahub_sdk import InfrahubClient

from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_no_duplicate_relationships, verify_no_edges_added_after_node_delete
from tests.constants import TestKind
from tests.helpers.schema import DEVICE_SCHEMA

from .shared import TestSchemaLifecycleBase


class TestSchemaLifecycleTemplateUpdate(TestSchemaLifecycleBase):
    @pytest.fixture(scope="class")
    def schema_network(self) -> dict[str, Any]:
        DEVICE_SCHEMA.version = "1.0"
        return DEVICE_SCHEMA.model_dump()

    @pytest.fixture(scope="class")
    def schema_node_server(self) -> dict[str, Any]:
        return SchemaRoot(
            version="1.0",
            generics=[],
            nodes=[
                NodeSchema(
                    name="Server",
                    namespace="Testing",
                    inherit_from=[TestKind.INTERFACE_HOLDER],
                    include_in_menu=True,
                    label="Server",
                    default_filter="name__value",
                    generate_template=True,
                    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
                )
            ],
        ).model_dump()

    async def test_step_01_create_branch(self, client: InfrahubClient) -> None:
        branch = await client.branch.create(branch_name="test", sync_with_git=False)
        assert branch

    async def test_step_02_load_schema(self, client: InfrahubClient, schema_network: dict[str, Any]) -> None:
        response = await client.schema.load(schemas=[schema_network], branch="test")
        assert not response.errors

    async def test_step_03_add_node_to_schema(
        self, db: InfrahubDatabase, client: InfrahubClient, schema_node_server: dict[str, Any]
    ) -> None:
        response = await client.schema.load(schemas=[schema_node_server], branch="test")
        assert not response.errors

    async def test_step_03_check_main_template(self, client: InfrahubClient) -> None:
        device_template = await client.schema.get(kind=f"Template{TestKind.DEVICE}", branch="test")
        assert device_template.human_friendly_id == ["template_name__value"]
        assert len(device_template.uniqueness_constraints) == 1
        assert device_template.uniqueness_constraints[0] == ["template_name__value"]

    async def test_step04_check_component_template(self, client: InfrahubClient) -> None:
        physical_interface_template = await client.schema.get(
            kind=f"Template{TestKind.PHYSICAL_INTERFACE}", branch="test"
        )
        assert physical_interface_template.human_friendly_id == ["device__template_name__value", "template_name__value"]
        assert len(physical_interface_template.uniqueness_constraints) == 1
        assert physical_interface_template.uniqueness_constraints[0] == ["template_name__value", "device"]

    async def test_final_validate(self, db: InfrahubDatabase) -> None:
        await verify_no_duplicate_relationships(db=db)
        await verify_no_edges_added_after_node_delete(db=db)
