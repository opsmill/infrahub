import json
from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.constants import RelationshipCardinality
from infrahub.core.migrations.graph.m042_create_hfid_display_label_in_db import Migration042
from infrahub.core.migrations.graph.m043_backfill_hfid_display_label_in_db import Migration043
from infrahub.core.node import Node
from infrahub.core.query.node import NodeListGetAttributeQuery
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubApp


class TestMigration042(TestInfrahubApp):
    @pytest.fixture
    def primary_thing_schema(self) -> NodeSchema:
        return NodeSchema(
            name="Thing",
            namespace="Primary",
            display_labels=["name__value", "color__value"],
            human_friendly_id=["name__value", "secondary__color__value", "secondary__size__value"],
            uniqueness_constraints=[["name__value"]],
            attributes=[
                AttributeSchema(name="name", kind="Text"),
                AttributeSchema(name="color", kind="Text"),
                AttributeSchema(name="size", kind="Number"),
            ],
            relationships=[
                RelationshipSchema(
                    name="secondary",
                    optional=False,
                    peer="SecondaryThing",
                    cardinality=RelationshipCardinality.ONE,
                )
            ],
        )

    @pytest.fixture
    def secondary_thing_schema(self) -> NodeSchema:
        return NodeSchema(
            name="Thing",
            namespace="Secondary",
            attributes=[
                AttributeSchema(name="name", kind="Text"),
                AttributeSchema(name="color", kind="Text"),
                AttributeSchema(name="size", kind="Number"),
            ],
        )

    @pytest.fixture
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        primary_thing_schema: NodeSchema,
        secondary_thing_schema: NodeSchema,
    ) -> dict[str, Node]:
        await load_schema(
            db=db,
            schema=SchemaRoot(nodes=[primary_thing_schema, secondary_thing_schema]),
            branch_name=default_branch.name,
            update_db=True,
        )
        primary_thing_schema = registry.schema.get_node_schema(name="PrimaryThing", branch=default_branch)
        secondary_thing_schema = registry.schema.get_node_schema(name="SecondaryThing", branch=default_branch)
        # just saving and loading these two schemas speeds up the test
        small_schema_branch = SchemaBranch(
            cache={
                primary_thing_schema.kind: primary_thing_schema,
                secondary_thing_schema.kind: secondary_thing_schema,
            },
            name=default_branch.name,
        )
        await registry.schema.load_schema_to_db(db=db, schema=small_schema_branch)

        # create secondary things
        secondary_thing = await Node.init(db=db, schema=secondary_thing_schema)
        await secondary_thing.new(db=db, name="secondary_thing_1", color="not red", size=-1)
        await secondary_thing.save(db=db)

        # create_primary_things
        primary_thing = await Node.init(db=db, schema=primary_thing_schema)
        await primary_thing.new(db=db, name="primary_thing_1", color="red", size=1, secondary=secondary_thing)
        await primary_thing.save(db=db)

        return {
            "secondary_thing": secondary_thing,
            "primary_thing": primary_thing,
        }

    async def erase_hfid_and_display_label(self, db: InfrahubDatabase) -> Node:
        query = """
MATCH (attr:Attribute)
WHERE attr.name in ["human_friendly_id", "display_label"]
DETACH DELETE attr
        """
        await db.execute_query(query=query)

    async def get_attribute_values_from_db(
        self, db: InfrahubDatabase, branch: Branch, attribute_names: list[str], node_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        query = await NodeListGetAttributeQuery.init(
            db=db,
            ids=node_ids,
            fields={attr_name: {True} for attr_name in attribute_names},
            branch=branch,
        )
        await query.execute(db=db)
        node_attributes_map = query.get_attributes_group_by_node()
        result_map = {}
        for node_id in node_ids:
            result_map[node_id] = {}
            for attr_name in attribute_names:
                result_map[node_id][attr_name] = node_attributes_map[node_id].attrs[attr_name].value
        return result_map

    async def test_migration_042_043(
        self, db: InfrahubDatabase, default_branch: Branch, initial_dataset: dict[str, Node]
    ) -> None:
        await self.erase_hfid_and_display_label(db=db)

        # test adding display label and HFID attributes
        async with db.start_session() as dbs:
            migration = Migration042(migrations=[])
            execution_result = await migration.execute(db=dbs)
            assert not execution_result.errors

            validation_result = await migration.validate_migration(db=dbs)
            assert not validation_result.errors

        # test backfilling display label and HFID attributes
        async with db.start_session() as dbs:
            migration = Migration043()
            execution_result = await migration.execute(db=dbs)
            assert not execution_result.errors

            validation_result = await migration.validate_migration(db=dbs)
            assert not validation_result.errors

        attribute_values_map = await self.get_attribute_values_from_db(
            db=db,
            branch=default_branch,
            attribute_names=["human_friendly_id", "display_label"],
            node_ids=[initial_dataset["primary_thing"].id, initial_dataset["secondary_thing"].id],
        )
        assert attribute_values_map[initial_dataset["primary_thing"].id]["display_label"] == "primary_thing_1 red"
        assert json.loads(attribute_values_map[initial_dataset["primary_thing"].id]["human_friendly_id"]) == [
            "primary_thing_1",
            "not red",
            "-1",
        ]


# TODO: test added/updated/removed nodes on default branch
# TODO: test added/updated/removed nodes on branch
# TODO: test updating relationships and values of peers
# TODO: test relationships with same name going different directions
# TODO: test branch-agnostic attributes and relationships
# TODO: test display labels and HFIDs updated on a branch with the same value on main
