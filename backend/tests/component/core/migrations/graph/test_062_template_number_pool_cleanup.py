from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, MetadataOptions
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m062_template_number_pool_cleanup import Migration062
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema, SchemaRoot
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


DEVICE_SCHEMA: dict = {
    "nodes": [
        {
            "name": "Device",
            "namespace": "Test",
            "default_filter": "name__value",
            "display_labels": ["name__value"],
            "generate_template": True,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "vlan_id", "kind": "Number", "optional": True},
                {"name": "description", "kind": "Text", "optional": True},
            ],
        }
    ]
}


class TestMigration062(TestInfrahubApp):
    @staticmethod
    async def get_default_branch_attr_value_from_db(db: InfrahubDatabase, node_uuid: str, attr_name: str) -> str | None:
        """Read the raw attribute value from the DB on the default branch, bypassing ORM deserialization.

        Only looks at edges on the default branch (main). Not suitable for branch-scoped assertions.
        """
        query = """
        MATCH (n:Node {uuid: $node_uuid})-[ha:HAS_ATTRIBUTE]->(a:Attribute {name: $attr_name})
        WHERE ha.branch = $branch AND ha.status = "active" AND ha.to IS NULL
        MATCH (a)-[hv:HAS_VALUE]->(av:AttributeValue)
        WHERE hv.branch = $branch AND hv.status = "active" AND hv.to IS NULL
        RETURN av.value AS value
        ORDER BY hv.from DESC
        LIMIT 1
        """
        results = await db.execute_query(
            query=query,
            params={"node_uuid": node_uuid, "attr_name": attr_name, "branch": registry.default_branch},
        )
        if results:
            return results[0][0]
        return None

    @pytest.fixture
    async def device_schema(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
    ) -> NodeSchema:
        schema = SchemaRoot(**DEVICE_SCHEMA)
        registry.schema.register_schema(schema=schema, branch=default_branch.name)
        return registry.schema.get_node_schema(name="TestDevice", branch=default_branch.name, duplicate=False)

    @pytest.fixture
    async def number_pool(self, db: InfrahubDatabase, device_schema: NodeSchema) -> Node:
        existing = await NodeManager.query(
            db=db,
            schema=InfrahubKind.NUMBERPOOL,
            filters={"node__value": "TestDevice", "node_attribute__value": "vlan_id"},
        )
        if existing:
            return existing[0]

        pool = await Node.init(db=db, schema=InfrahubKind.NUMBERPOOL)
        await pool.new(
            db=db,
            name="test-vlan-pool",
            node="TestDevice",
            node_attribute="vlan_id",
            start_range=100,
            end_range=200,
        )
        await pool.save(db=db)
        return pool

    @pytest.fixture
    async def template_with_pool_source(self, db: InfrahubDatabase, number_pool: Node) -> Node:
        template = await Node.init(db=db, schema="TemplateTestDevice")
        await template.new(
            db=db,
            template_name="pooled-device-template",
            vlan_id=150,
            description="a device from pool",
        )
        await template.save(db=db)

        # Set the number pool as source on vlan_id only (not description)
        loaded = await NodeManager.get_one(db=db, id=template.id, include_metadata=MetadataOptions.LINKED_NODES)
        loaded.vlan_id.source = number_pool.id
        await loaded.save(db=db, fields=["vlan_id"])
        return loaded

    @pytest.fixture
    async def template_without_pool_source(self, db: InfrahubDatabase, device_schema: NodeSchema) -> Node:
        template = await Node.init(db=db, schema="TemplateTestDevice")
        await template.new(
            db=db,
            template_name="plain-device-template",
            vlan_id=42,
            description="a plain device",
        )
        await template.save(db=db)
        return template

    async def test_nullifies_number_pool_attributes(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        number_pool: Node,
        template_with_pool_source: Node,
        template_without_pool_source: Node,
    ) -> None:
        # Verify initial values before migration
        assert await self.get_default_branch_attr_value_from_db(db, template_with_pool_source.id, "vlan_id") == 150
        assert (
            await self.get_default_branch_attr_value_from_db(db, template_with_pool_source.id, "description")
            == "a device from pool"
        )

        async with db.start_session() as dbs:
            migration = Migration062()
            result = await migration.execute(migration_input=MigrationInput(db=dbs))
            assert not result.errors

        # Pool-sourced attr should be set to "NULL" in the DB
        assert await self.get_default_branch_attr_value_from_db(db, template_with_pool_source.id, "vlan_id") == "NULL"
        # Non-pool-sourced attr on the same template should be unchanged
        assert (
            await self.get_default_branch_attr_value_from_db(db, template_with_pool_source.id, "description")
            == "a device from pool"
        )

        updated = await NodeManager.get_one(
            db=db,
            id=template_with_pool_source.id,
            branch=default_branch,
            include_metadata=MetadataOptions.LINKED_NODES,
        )
        assert updated.vlan_id.value is None
        assert updated.vlan_id.source_id == number_pool.id
        assert updated.description.value == "a device from pool"
        assert updated.description.source_id is None

        # Non-pool-sourced template: attrs unchanged, no source
        unchanged = await NodeManager.get_one(
            db=db,
            id=template_without_pool_source.id,
            branch=default_branch,
            include_metadata=MetadataOptions.LINKED_NODES,
        )
        assert unchanged.vlan_id.value == 42
        assert unchanged.vlan_id.source_id is None
        assert unchanged.description.value == "a plain device"
        assert unchanged.description.source_id is None

    async def test_idempotent(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        template_with_pool_source: Node,
    ) -> None:
        async with db.start_session() as dbs:
            migration = Migration062()
            result = await migration.execute(migration_input=MigrationInput(db=dbs))
            assert not result.errors

        async with db.start_session() as dbs:
            migration = Migration062()
            result = await migration.execute(migration_input=MigrationInput(db=dbs))
            assert not result.errors

        assert await self.get_default_branch_attr_value_from_db(db, template_with_pool_source.id, "vlan_id") == "NULL"

    async def test_execute_against_branch(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        device_schema: NodeSchema,
        number_pool: Node,
    ) -> None:
        test_branch = await create_branch(db=db, branch_name="test-branch-m062")

        template = await Node.init(db=db, schema="TemplateTestDevice", branch=test_branch)
        await template.new(
            db=db,
            template_name="branch-device-template",
            vlan_id=999,
        )
        await template.save(db=db)

        loaded = await NodeManager.get_one(
            db=db, id=template.id, branch=test_branch, include_metadata=MetadataOptions.LINKED_NODES
        )
        loaded.vlan_id.source = number_pool.id
        await loaded.save(db=db, fields=["vlan_id"])

        # Execute against default branch first (required before execute_against_branch)
        async with db.start_session() as dbs:
            migration = Migration062()
            await migration.execute(migration_input=MigrationInput(db=dbs))

        await test_branch.rebase(db=db)

        async with db.start_session() as dbs:
            migration = Migration062()
            result = await migration.execute_against_branch(migration_input=MigrationInput(db=dbs), branch=test_branch)
            assert not result.errors

        updated = await NodeManager.get_one(
            db=db,
            id=template.id,
            branch=test_branch,
            include_metadata=MetadataOptions.LINKED_NODES,
        )
        assert updated.vlan_id.value is None
        assert updated.vlan_id.source_id == number_pool.id
