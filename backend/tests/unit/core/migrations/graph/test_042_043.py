import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.constants import BranchSupportType, RelationshipCardinality, RelationshipDirection
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m042_create_hfid_display_label_in_db import Migration042
from infrahub.core.migrations.graph.m043_backfill_hfid_display_label_in_db import Migration043
from infrahub.core.node import Node
from infrahub.core.query.node import NodeListGetAttributeQuery
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_no_duplicate_relationships, verify_no_edges_added_after_node_delete
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubApp


class NodeStatus(StrEnum):
    ACTIVE = "active"
    DELETED = "deleted"


@dataclass
class NodeDetails:
    node: Node
    on_default_branch: bool
    display_label: str | None
    human_friendly_id: list[str] | None
    status: NodeStatus

    @property
    def is_active(self) -> bool:
        return self.status is NodeStatus.ACTIVE


class TestMigration042(TestInfrahubApp):
    @pytest.fixture
    def primary_thing_schema(self) -> NodeSchema:
        return NodeSchema(
            name="Thing",
            namespace="Primary",
            display_labels=["name__value", "color__value", "agnostic_smell__value"],
            human_friendly_id=[
                "name__value",
                "agnostic_smell__value",
                "secondary_in__name__value",
                "secondary_out__size__value",
                "agnostic_secondary__agnostic_smell__value",
            ],
            uniqueness_constraints=[["name__value"]],
            attributes=[
                AttributeSchema(name="name", kind="Text"),
                AttributeSchema(name="color", kind="Text"),
                AttributeSchema(name="size", kind="Number"),
                AttributeSchema(name="agnostic_smell", kind="Text", branch=BranchSupportType.AGNOSTIC),
            ],
            relationships=[
                RelationshipSchema(
                    name="secondary_in",
                    optional=False,
                    peer="SecondaryThing",
                    cardinality=RelationshipCardinality.ONE,
                    direction=RelationshipDirection.INBOUND,
                    identifier="secondary__oneway",
                ),
                RelationshipSchema(
                    name="secondary_out",
                    optional=False,
                    peer="SecondaryThing",
                    cardinality=RelationshipCardinality.ONE,
                    direction=RelationshipDirection.OUTBOUND,
                    identifier="secondary__oneway",
                ),
                RelationshipSchema(
                    name="agnostic_secondary",
                    optional=False,
                    peer="SecondaryThing",
                    cardinality=RelationshipCardinality.ONE,
                    branch=BranchSupportType.AGNOSTIC,
                ),
            ],
        )

    @pytest.fixture
    def secondary_thing_schema(self) -> NodeSchema:
        return NodeSchema(
            name="Thing",
            namespace="Secondary",
            display_labels=["name__value", "size__value"],
            human_friendly_id=["name__value", "color__value", "agnostic_smell__value"],
            attributes=[
                AttributeSchema(name="name", kind="Text"),
                AttributeSchema(name="color", kind="Text"),
                AttributeSchema(name="size", kind="Number"),
                AttributeSchema(name="agnostic_smell", kind="Text", branch=BranchSupportType.AGNOSTIC),
            ],
        )

    @pytest.fixture
    async def load_schemas(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        primary_thing_schema: NodeSchema,
        secondary_thing_schema: NodeSchema,
    ) -> SchemaBranch:
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
        return registry.schema.get_schema_branch(name=default_branch.name)

    @pytest.fixture
    async def branch(self, db: InfrahubDatabase, default_branch: Branch) -> Branch:
        return await create_branch(db=db, branch_name="migration-test-branch")

    @pytest.fixture
    async def secondary_thing_one_details(self, db: InfrahubDatabase, load_schemas: SchemaBranch) -> NodeDetails:
        secondary_thing = await Node.init(db=db, schema="SecondaryThing")
        await secondary_thing.new(db=db, name="secondary_thing_1", color="not red", size=-1, agnostic_smell="okay")
        await secondary_thing.save(db=db)
        return NodeDetails(
            node=secondary_thing,
            on_default_branch=True,
            display_label=f"{secondary_thing.name.value} {secondary_thing.size.value}",
            human_friendly_id=[
                str(v)
                for v in (secondary_thing.name.value, secondary_thing.color.value, secondary_thing.agnostic_smell.value)
            ],
            status=NodeStatus.ACTIVE,
        )

    @pytest.fixture
    async def secondary_thing_two_details(self, db: InfrahubDatabase, load_schemas: SchemaBranch) -> NodeDetails:
        secondary_thing = await Node.init(db=db, schema="SecondaryThing")
        await secondary_thing.new(
            db=db, name="secondary_thing_2", color="orange", size=42, agnostic_smell="pretty good"
        )
        await secondary_thing.save(db=db)
        return NodeDetails(
            node=secondary_thing,
            on_default_branch=True,
            display_label=f"{secondary_thing.name.value} {secondary_thing.size.value}",
            human_friendly_id=[
                str(v)
                for v in (secondary_thing.name.value, secondary_thing.color.value, secondary_thing.agnostic_smell.value)
            ],
            status=NodeStatus.ACTIVE,
        )

    @pytest.fixture
    async def secondary_thing_three_agnostic_value_update(self) -> str:
        return "more okay"

    @pytest.fixture
    async def secondary_thing_three_details(
        self, db: InfrahubDatabase, load_schemas: SchemaBranch, secondary_thing_three_agnostic_value_update: str
    ) -> NodeDetails:
        secondary_thing = await Node.init(db=db, schema="SecondaryThing")
        await secondary_thing.new(db=db, name="secondary_thing_3", color="inidigo", size=53, agnostic_smell="quite bad")
        await secondary_thing.save(db=db)
        secondary_thing.color.value = "indigogo"
        secondary_thing.size.value = 54
        secondary_thing.agnostic_smell.value = "really quite bad"
        await secondary_thing.save(db=db)

        return NodeDetails(
            node=secondary_thing,
            on_default_branch=True,
            display_label=f"{secondary_thing.name.value} {secondary_thing.size.value}",
            human_friendly_id=[
                str(v)
                for v in (
                    secondary_thing.name.value,
                    secondary_thing.color.value,
                    secondary_thing_three_agnostic_value_update,
                )
            ],
            status=NodeStatus.ACTIVE,
        )

    @pytest.fixture
    async def primary_thing_one_agnostic_value_update(self) -> str:
        return "very lilac"

    @pytest.fixture
    async def primary_thing_one_details(
        self,
        db: InfrahubDatabase,
        load_schemas: SchemaBranch,
        secondary_thing_one_details: NodeDetails,
        secondary_thing_two_details: NodeDetails,
        secondary_thing_three_details: NodeDetails,
        secondary_thing_three_agnostic_value_update: str,
        primary_thing_one_agnostic_value_update: str,
    ) -> NodeDetails:
        secondary_one_node = secondary_thing_one_details.node
        secondary_two_node = secondary_thing_two_details.node
        secondary_three_node = secondary_thing_three_details.node
        primary_thing = await Node.init(db=db, schema="PrimaryThing")
        await primary_thing.new(
            db=db,
            name="primary_thing_1",
            color="red",
            size=1,
            agnostic_smell="lilac",
            secondary_in=secondary_one_node,
            secondary_out=secondary_two_node,
            agnostic_secondary=secondary_three_node,
        )
        await primary_thing.save(db=db)
        return NodeDetails(
            node=primary_thing,
            on_default_branch=True,
            display_label=f"{primary_thing.name.value} {primary_thing.color.value} {primary_thing_one_agnostic_value_update}",
            human_friendly_id=[
                str(v)
                for v in (
                    primary_thing.name.value,
                    primary_thing_one_agnostic_value_update,
                    secondary_one_node.name.value,
                    secondary_two_node.size.value,
                    secondary_thing_three_agnostic_value_update,
                )
            ],
            status=NodeStatus.ACTIVE,
        )

    @pytest.fixture
    async def primary_thing_two_main_update_details(
        self,
        db: InfrahubDatabase,
        load_schemas: SchemaBranch,
        secondary_thing_one_details: NodeDetails,
        secondary_thing_two_details: NodeDetails,
        secondary_thing_three_details: NodeDetails,
    ) -> NodeDetails:
        primary_thing = await Node.init(db=db, schema="PrimaryThing")
        await primary_thing.new(
            db=db,
            name="primary_thing_2",
            color="yellow",
            size=2,
            agnostic_smell="violet",
            secondary_in=secondary_thing_two_details.node,
            secondary_out=secondary_thing_three_details.node,
            agnostic_secondary=secondary_thing_one_details.node,
        )
        await primary_thing.save(db=db)

        new_secondary_in_node = secondary_thing_three_details.node
        new_secondary_out_node = secondary_thing_one_details.node
        new_agnostic_secondary_node = secondary_thing_two_details.node
        primary_thing.color.value = "double yellow"
        primary_thing.agnostic_smell.value = "ultra violet"
        await primary_thing.secondary_in.update(db=db, data=new_secondary_in_node)
        await primary_thing.secondary_out.update(db=db, data=new_secondary_out_node)
        await primary_thing.agnostic_secondary.update(db=db, data=new_agnostic_secondary_node)
        await primary_thing.save(db=db)

        return NodeDetails(
            node=primary_thing,
            on_default_branch=True,
            # a bug in deleting branch-aware nodes with branch-agnostic relationships prevents this from working correctly
            # https://github.com/opsmill/infrahub/issues/7513
            # display_label=f"{primary_thing.name.value} {primary_thing.color.value} {primary_thing.agnostic_smell.value}",
            display_label=f"{primary_thing.name.value} {primary_thing.color.value}",
            human_friendly_id=[
                str(primary_thing.name.value),
                # https://github.com/opsmill/infrahub/issues/7513 here too
                # primary_thing.agnostic_smell.value,
                None,
                str(new_secondary_in_node.name.value),
                str(new_secondary_out_node.size.value),
                str(new_agnostic_secondary_node.agnostic_smell.value),
            ],
            status=NodeStatus.ACTIVE,
        )

    @pytest.fixture
    async def primary_thing_three_deleted_details(
        self,
        db: InfrahubDatabase,
        load_schemas: SchemaBranch,
        secondary_thing_two_details: NodeDetails,
        secondary_thing_three_details: NodeDetails,
    ) -> NodeDetails:
        primary_thing = await Node.init(db=db, schema="PrimaryThing")
        await primary_thing.new(
            db=db,
            name="primary_thing_3",
            color="green",
            agnostic_smell="emerald",
            size=3,
            secondary_in=secondary_thing_two_details.node,
            secondary_out=secondary_thing_three_details.node,
            agnostic_secondary=secondary_thing_two_details.node,
        )
        await primary_thing.save(db=db)
        await primary_thing.delete(db=db)
        return NodeDetails(
            node=primary_thing,
            on_default_branch=True,
            display_label=None,
            human_friendly_id=None,
            status=NodeStatus.DELETED,
        )

    # --------------------------------
    # Branch creates, updates, deletes
    # --------------------------------

    @pytest.fixture
    async def secondary_thing_three_branch_update_details(
        self,
        db: InfrahubDatabase,
        load_schemas: SchemaBranch,
        branch: Branch,
        secondary_thing_three_details: NodeDetails,
        secondary_thing_three_agnostic_value_update: str,
    ) -> NodeDetails:
        secondary_thing = await NodeManager.get_one(db=db, branch=branch, id=secondary_thing_three_details.node.id)
        secondary_thing.color.value = "indigogogo-branch"
        secondary_thing.size.value = 55
        secondary_thing.agnostic_smell.value = secondary_thing_three_agnostic_value_update
        await secondary_thing.save(db=db)

        return NodeDetails(
            node=secondary_thing,
            on_default_branch=False,
            display_label=f"{secondary_thing.name.value} {secondary_thing.size.value}",
            human_friendly_id=[
                str(v)
                for v in (
                    secondary_thing.name.value,
                    secondary_thing.color.value,
                    secondary_thing_three_agnostic_value_update,
                )
            ],
            status=NodeStatus.ACTIVE,
        )

    @pytest.fixture
    async def primary_thing_one_branch_details(
        self,
        db: InfrahubDatabase,
        load_schemas: SchemaBranch,
        secondary_thing_one_details: NodeDetails,
        secondary_thing_two_details: NodeDetails,
        branch: Branch,
    ) -> NodeDetails:
        primary_thing = await Node.init(db=db, schema="PrimaryThing", branch=branch)
        await primary_thing.new(
            db=db,
            name="primary_thing_1_branch",
            color="blue",
            agnostic_smell="blueberry",
            size=1,
            secondary_in=secondary_thing_one_details.node,
            secondary_out=secondary_thing_two_details.node,
            agnostic_secondary=secondary_thing_two_details.node,
        )
        await primary_thing.save(db=db)
        return NodeDetails(
            node=primary_thing,
            on_default_branch=False,
            display_label=f"{primary_thing.name.value} {primary_thing.color.value} {primary_thing.agnostic_smell.value}",
            human_friendly_id=[
                str(v)
                for v in (
                    primary_thing.name.value,
                    primary_thing.agnostic_smell.value,
                    secondary_thing_one_details.node.name.value,
                    secondary_thing_two_details.node.size.value,
                    secondary_thing_two_details.node.agnostic_smell.value,
                )
            ],
            status=NodeStatus.ACTIVE,
        )

    @pytest.fixture
    async def primary_thing_two_deleted_on_branch_details(
        self,
        db: InfrahubDatabase,
        load_schemas: SchemaBranch,
        primary_thing_two_main_update_details: NodeDetails,
        branch: Branch,
    ) -> NodeDetails:
        primary_thing = await NodeManager.get_one(
            db=db, branch=branch, id=primary_thing_two_main_update_details.node.id
        )
        await primary_thing.delete(db=db)
        return NodeDetails(
            node=primary_thing,
            on_default_branch=False,
            display_label=None,
            human_friendly_id=None,
            status=NodeStatus.DELETED,
        )

    @pytest.fixture
    async def primary_thing_one_branch_update_details(
        self,
        db: InfrahubDatabase,
        load_schemas: SchemaBranch,
        primary_thing_one_details: NodeDetails,
        branch: Branch,
        secondary_thing_three_branch_update_details: NodeDetails,
        primary_thing_one_agnostic_value_update: str,
        secondary_thing_three_agnostic_value_update: str,
    ) -> NodeDetails:
        primary_thing = await NodeManager.get_one(db=db, branch=branch, id=primary_thing_one_details.node.id)
        # Update some attributes on the branch
        primary_thing.color.value = "purple"
        primary_thing.size.value = 999
        primary_thing.agnostic_smell.value = primary_thing_one_agnostic_value_update
        # update secondary relationship on branch
        new_secondary_in_node = secondary_thing_three_branch_update_details.node
        current_secondary_out_node = await primary_thing.secondary_out.get_peer(db=db)
        await primary_thing.secondary_in.update(db=db, data=new_secondary_in_node)
        await primary_thing.save(db=db)
        return NodeDetails(
            node=primary_thing,
            on_default_branch=False,
            display_label=f"{primary_thing.name.value} {primary_thing.color.value} {primary_thing_one_agnostic_value_update}",
            human_friendly_id=[
                str(v)
                for v in (
                    primary_thing.name.value,
                    primary_thing_one_agnostic_value_update,
                    new_secondary_in_node.name.value,
                    current_secondary_out_node.size.value,
                    secondary_thing_three_agnostic_value_update,
                )
            ],
            status=NodeStatus.ACTIVE,
        )

    @pytest.fixture
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        load_schemas: SchemaBranch,
        secondary_thing_one_details: NodeDetails,
        secondary_thing_two_details: NodeDetails,
        secondary_thing_three_details: NodeDetails,
        primary_thing_one_details: NodeDetails,
        primary_thing_two_main_update_details: NodeDetails,
        primary_thing_two_deleted_on_branch_details: NodeDetails,
        primary_thing_three_deleted_details: NodeDetails,
        branch: Branch,
        secondary_thing_three_branch_update_details: NodeDetails,
        primary_thing_one_branch_details: NodeDetails,
        primary_thing_one_branch_update_details: NodeDetails,
    ) -> dict[str, NodeDetails]:
        return {
            "secondary_thing_one": secondary_thing_one_details,
            "secondary_thing_two": secondary_thing_two_details,
            "secondary_thing_three": secondary_thing_three_details,
            "primary_thing_one": primary_thing_one_details,
            "primary_thing_two": primary_thing_two_main_update_details,
            "primary_thing_two_deleted_on_branch": primary_thing_two_deleted_on_branch_details,
            "primary_thing_three_deleted": primary_thing_three_deleted_details,
            "secondary_thing_three_branch_update": secondary_thing_three_branch_update_details,
            "primary_thing_one_branch": primary_thing_one_branch_details,
            "primary_thing_one_updated_on_branch": primary_thing_one_branch_update_details,
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
            if node_id not in node_attributes_map:
                continue
            result_map[node_id] = {}
            for attr_name in attribute_names:
                result_map[node_id][attr_name] = node_attributes_map[node_id].attrs[attr_name].value
        return result_map

    async def test_migration_042_043(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initial_dataset: dict[str, NodeDetails],
        branch: Branch,
        primary_thing_schema: NodeSchema,
        secondary_thing_schema: NodeSchema,
    ) -> None:
        await self.erase_hfid_and_display_label(db=db)

        # test adding display label and HFID attributes on default branch
        async with db.start_session() as dbs:
            migration = Migration042(migrations=[])
            execution_result = await migration.execute(db=dbs)
            assert not execution_result.errors

            validation_result = await migration.validate_migration(db=dbs)
            assert not validation_result.errors

        # test backfilling display label and HFID attributes on default branch
        async with db.start_session() as dbs:
            migration = Migration043()
            execution_result = await migration.execute(db=dbs)
            assert not execution_result.errors

            validation_result = await migration.validate_migration(db=dbs)
            assert not validation_result.errors

        # validate updates on default branch
        attribute_values_map_main = await self.get_attribute_values_from_db(
            db=db,
            branch=default_branch,
            attribute_names=["human_friendly_id", "display_label"],
            node_ids=[node_details.node.id for node_details in initial_dataset.values()],
        )
        expected_ids = {
            node_details.node.id
            for node_details in initial_dataset.values()
            if node_details.is_active and node_details.on_default_branch
        }
        assert set(attribute_values_map_main.keys()) == expected_ids
        for node_details in initial_dataset.values():
            if not node_details.is_active or not node_details.on_default_branch:
                continue
            assert attribute_values_map_main[node_details.node.id]["display_label"] == node_details.display_label
            assert (
                json.loads(attribute_values_map_main[node_details.node.id]["human_friendly_id"])
                == node_details.human_friendly_id
            )

        # rebase and migrate branch
        await branch.rebase(db=db)
        async with db.start_session() as dbs:
            migration = Migration042(migrations=[])
            execution_result = await migration.execute_against_branch(db=dbs, branch=branch)
            assert not execution_result.errors

        branch_schema_branch = SchemaBranch(
            cache={},
            name=branch.name,
        )
        branch_schema_branch.set(name="PrimaryThing", schema=primary_thing_schema)
        branch_schema_branch.set(name="SecondaryThing", schema=secondary_thing_schema)
        for internal_schema_kind in ["SchemaNode", "SchemaAttribute", "SchemaRelationship", "SchemaGeneric"]:
            branch_schema_branch.set(
                name=internal_schema_kind,
                schema=registry.schema.get(name=internal_schema_kind, branch=default_branch, duplicate=False),
            )
        branch_schema_branch.process()
        registry.schema.set_schema_branch(name=branch.name, schema=branch_schema_branch)

        async with db.start_session() as dbs:
            migration = Migration043()
            execution_result = await migration.execute_against_branch(db=dbs, branch=branch)
            assert not execution_result.errors

        attribute_values_map_branch = await self.get_attribute_values_from_db(
            db=db,
            branch=branch,
            attribute_names=["human_friendly_id", "display_label"],
            node_ids=[
                node_details.node.id for node_details in initial_dataset.values() if not node_details.on_default_branch
            ],
        )
        expected_ids = {
            node_details.node.id
            for node_details in initial_dataset.values()
            if node_details.is_active and not node_details.on_default_branch
        }

        # bug in rebase allows attributes added on main to persist on a node that is deleted on a branch
        expected_ids.add(initial_dataset["primary_thing_two_deleted_on_branch"].node.id)

        assert set(attribute_values_map_branch.keys()) == expected_ids
        for node_details in initial_dataset.values():
            if not node_details.is_active or node_details.on_default_branch:
                continue
            assert attribute_values_map_branch[node_details.node.id]["display_label"] == node_details.display_label
            assert (
                json.loads(attribute_values_map_branch[node_details.node.id]["human_friendly_id"])
                == node_details.human_friendly_id
            )

        await verify_no_edges_added_after_node_delete(db=db)
        await verify_no_duplicate_relationships(db=db)


# TODO: test display labels and HFIDs updated on a branch with the same value on main
# TODO: test HFID/display labels update on branch
