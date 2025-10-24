import copy

import pytest

from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m042_create_hfid_display_label_in_db import Migration042
from infrahub.core.migrations.graph.m043_backfill_hfid_display_label_in_db import Migration043
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from tests.helpers.schema import WIDGET, load_schema
from tests.helpers.test_app import TestInfrahubApp

QUERY_HFID = """
MATCH (n:TestingWidget)-[:HAS_ATTRIBUTE]->(a:Attribute)-[:HAS_VALUE]->(v:AttributeValue)
WHERE a.name = "human_friendly_id"
RETURN n, v
"""

QUERY_DISPLAY_LABEL = """
MATCH (n:TestingWidget)-[:HAS_ATTRIBUTE]->(a:Attribute)-[:HAS_VALUE]->(v:AttributeValue)
WHERE a.name = "display_label"
RETURN n, v
"""


class TestMigration042(TestInfrahubApp):
    @pytest.fixture
    async def initial_dataset(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
    ) -> dict[str, Node]:
        await load_schema(db=db, schema=SchemaRoot(nodes=[WIDGET]), branch_name=default_branch.name, update_db=True)
        widget_schema = registry.schema.get_node_schema(name=WIDGET.kind, branch=default_branch)
        # just saving and loading this one schema speeds up the test
        widget_only_schema_branch = SchemaBranch(cache={widget_schema.kind: widget_schema}, name=default_branch.name)
        await registry.schema.load_schema_to_db(db=db, schema=widget_only_schema_branch)

        nodes: dict[str, Node] = {}
        for name in [
            "widget_alpha",
            "widget_bravo",
            "widget_charlie",
            "widget_delta",
            "widget_echo",
            "widget_foxtrot",
            "widget_golf",
            "widget_hotel",
            "widget_india",
            "widget_juliet",
        ]:
            node = await Node.init(db=db, schema=widget_schema)
            await node.new(db=db, name=name)
            await node.save(db=db)

            nodes[name] = node

        return nodes

    async def test_migration_042_043(
        self, db: InfrahubDatabase, default_branch: Branch, initial_dataset: dict[str, Node]
    ) -> None:
        results = await db.execute_query(query=QUERY_HFID)
        assert not results

        unique_name_widget = copy.deepcopy(WIDGET)
        unique_name_widget.human_friendly_id = ["name__value"]
        unique_name_widget.get_attribute(name="name").unique = True
        await load_schema(db=db, schema=SchemaRoot(nodes=[unique_name_widget]), update_db=True)

        results = await db.execute_query(query=QUERY_HFID)
        assert not results

        async with db.start_session() as dbs:
            migration = Migration042(migrations=[])
            execution_result = await migration.execute(db=dbs)
            assert not execution_result.errors

            validation_result = await migration.validate_migration(db=dbs)
            assert not validation_result.errors

        async with db.start_session() as dbs:
            migration = Migration043()
            execution_result = await migration.execute(db=dbs)
            assert not execution_result.errors

            validation_result = await migration.validate_migration(db=dbs)
            assert not validation_result.errors

        results = await db.execute_query(query=QUERY_HFID)
        assert results

        schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        registry.schema.set_schema_branch(name=default_branch.name, schema=schema_branch)
        nodes: list[Node] = await NodeManager.query(db=db, schema=WIDGET.kind)
        assert len(nodes) == 10
        assert nodes[0].has_human_friendly_id()
        assert await nodes[0].get_hfid(db=db) == [nodes[0].name.value]
