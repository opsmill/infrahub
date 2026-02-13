from typing import Any

import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.schema.main import GenericSchemaAPI, TemplateSchemaAPI

from infrahub.core.constants import OBJECT_TEMPLATE_RELATIONSHIP_NAME
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_no_duplicate_relationships, verify_no_edges_added_after_node_delete
from tests.helpers.test_app import TestInfrahubApp


class TestSchemaTemplateGenericInheritance(TestInfrahubApp):
    """Test that object_template relationships get the correct peer when both a
    GenericSchema and a NodeSchema inheriting from it have generate_template=True."""

    @pytest.fixture(scope="class")
    def schema_generic_and_node(self) -> dict[str, Any]:
        return SchemaRoot(
            version="1.0",
            generics=[
                GenericSchema(
                    name="MyGeneric",
                    namespace="Testing",
                    generate_template=True,
                    attributes=[
                        AttributeSchema(name="generic_attr", kind="Text", optional=True),
                    ],
                ),
            ],
            nodes=[
                NodeSchema(
                    name="MyNode",
                    namespace="Testing",
                    inherit_from=["TestingMyGeneric"],
                    generate_template=True,
                    attributes=[
                        AttributeSchema(name="name", kind="Text"),
                    ],
                ),
            ],
        ).model_dump()

    @pytest.fixture(scope="class")
    def schema_new_node(self) -> dict[str, Any]:
        return SchemaRoot(
            version="1.0",
            nodes=[
                NodeSchema(
                    name="MyOtherNode",
                    namespace="Testing",
                    inherit_from=["TestingMyGeneric"],
                    generate_template=True,
                    attributes=[
                        AttributeSchema(name="name", kind="Text"),
                    ],
                ),
            ],
        ).model_dump()

    async def test_step_01_load_schema_with_generic_and_node(
        self, client: InfrahubClient, schema_generic_and_node: dict[str, Any]
    ) -> None:
        """Load a Generic and a Node that inherits from it, both with generate_template=True."""
        response = await client.schema.load(schemas=[schema_generic_and_node])
        assert not response.errors

    async def test_step_02_validate_object_template_peers(self, client: InfrahubClient) -> None:
        """Each schema's object_template should point to its own template, not the generic's."""
        generic_schema = await client.schema.get(kind="TestingMyGeneric")
        generic_template_rel = next(
            r for r in generic_schema.relationships if r.name == OBJECT_TEMPLATE_RELATIONSHIP_NAME
        )
        assert generic_template_rel.inherited is False
        assert generic_template_rel.peer == "TemplateTestingMyGeneric"

        node_schema = await client.schema.get(kind="TestingMyNode")
        node_template_rel = next(r for r in node_schema.relationships if r.name == OBJECT_TEMPLATE_RELATIONSHIP_NAME)
        assert node_template_rel.inherited is False
        assert node_template_rel.peer == "TemplateTestingMyNode"

        # The template for a GenericSchema should be a GenericSchemaAPI (not a TemplateSchemaAPI)
        generic_template = await client.schema.get(kind="TemplateTestingMyGeneric")
        assert isinstance(generic_template, GenericSchemaAPI)
        assert not isinstance(generic_template, TemplateSchemaAPI)

        # The template for a NodeSchema should be a TemplateSchemaAPI (not a GenericSchemaAPI)
        node_template = await client.schema.get(kind="TemplateTestingMyNode")
        assert isinstance(node_template, TemplateSchemaAPI)
        assert not isinstance(node_template, GenericSchemaAPI)

    async def test_step_03_load_new_node_inheriting_from_generic(
        self, client: InfrahubClient, schema_new_node: dict[str, Any]
    ) -> None:
        """Add a second Node inheriting from the same Generic, also with generate_template=True."""
        response = await client.schema.load(schemas=[schema_new_node])
        assert not response.errors

    async def test_step_04_validate_all_object_template_peers(self, client: InfrahubClient) -> None:
        """All three schemas should have object_template pointing to their own template."""
        generic_schema = await client.schema.get(kind="TestingMyGeneric")
        generic_template_rel = next(
            r for r in generic_schema.relationships if r.name == OBJECT_TEMPLATE_RELATIONSHIP_NAME
        )
        assert generic_template_rel.inherited is False
        assert generic_template_rel.peer == "TemplateTestingMyGeneric"

        node_schema = await client.schema.get(kind="TestingMyNode")
        node_template_rel = next(r for r in node_schema.relationships if r.name == OBJECT_TEMPLATE_RELATIONSHIP_NAME)
        assert node_template_rel.inherited is False
        assert node_template_rel.peer == "TemplateTestingMyNode"

        other_node_schema = await client.schema.get(kind="TestingMyOtherNode")
        other_node_template_rel = next(
            r for r in other_node_schema.relationships if r.name == OBJECT_TEMPLATE_RELATIONSHIP_NAME
        )
        assert other_node_template_rel.inherited is False
        assert other_node_template_rel.peer == "TemplateTestingMyOtherNode"

        # Verify template types are correct after adding the second node
        generic_template = await client.schema.get(kind="TemplateTestingMyGeneric")
        assert isinstance(generic_template, GenericSchemaAPI)

        node_template = await client.schema.get(kind="TemplateTestingMyNode")
        assert isinstance(node_template, TemplateSchemaAPI)

        other_node_template = await client.schema.get(kind="TemplateTestingMyOtherNode")
        assert isinstance(other_node_template, TemplateSchemaAPI)

    async def test_final_validate(self, db: InfrahubDatabase) -> None:
        await verify_no_duplicate_relationships(db=db)
        await verify_no_edges_added_after_node_delete(db=db)
