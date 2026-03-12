from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import (
    GLOBAL_BRANCH_NAME,
    BranchSupportType,
    RelationshipCardinality,
    RelationshipDirection,
)
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m059_fix_hfid_display_label_nulls import Migration059
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.timestamp import Timestamp
from tests.helpers.db_validation import verify_no_duplicate_paths
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class TestMigration059(TestInfrahubApp):
    """Test that Migration059 fixes bad display_label/HFID values across all branch types.

    display_label and human_friendly_id are computed NodePropertyAttributes, not directly
    settable via the Node API, so we inject bad values via raw Cypher.
    """

    @pytest.fixture
    def device_schema(self) -> NodeSchema:
        return NodeSchema(
            name="Device",
            namespace="Test",
            display_label="{{ name__value }} {{ role__name__value }}",
            human_friendly_id=["name__value", "role__name__value"],
            branch=BranchSupportType.AWARE,
            attributes=[
                AttributeSchema(name="name", kind="Text"),
            ],
            relationships=[
                RelationshipSchema(
                    name="role",
                    peer="TestRole",
                    optional=False,
                    cardinality=RelationshipCardinality.ONE,
                    direction=RelationshipDirection.OUTBOUND,
                ),
            ],
        )

    @pytest.fixture
    def role_schema(self) -> NodeSchema:
        return NodeSchema(
            name="Role",
            namespace="Test",
            display_label="name__value",
            branch=BranchSupportType.AWARE,
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
            ],
        )

    @pytest.fixture
    def agnostic_tag_schema(self) -> NodeSchema:
        return NodeSchema(
            name="Tag",
            namespace="Test",
            display_label="name__value",
            human_friendly_id=["name__value"],
            branch=BranchSupportType.AGNOSTIC,
            attributes=[
                AttributeSchema(name="name", kind="Text"),
            ],
        )

    @pytest.fixture
    async def loaded_schemas(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        device_schema: NodeSchema,
        role_schema: NodeSchema,
        agnostic_tag_schema: NodeSchema,
    ) -> SchemaBranch:
        await load_schema(
            db=db,
            schema=SchemaRoot(nodes=[device_schema, role_schema, agnostic_tag_schema]),
            branch_name=default_branch.name,
            update_db=True,
        )
        return registry.schema.get_schema_branch(name=default_branch.name)

    async def _get_display_label(self, db: InfrahubDatabase, branch: Branch, node_id: str) -> str:
        node = await NodeManager.get_one(db=db, id=node_id, branch=branch)
        return await node.get_display_label(db=db)

    async def _get_hfid(self, db: InfrahubDatabase, branch: Branch, node_id: str) -> list[str] | None:
        node = await NodeManager.get_one(db=db, id=node_id, branch=branch)
        return await node.get_hfid(db=db)

    async def _set_bad_attribute_value(
        self, db: InfrahubDatabase, node_id: str, attr_name: str, bad_value: str, branch_name: str
    ) -> None:
        """Expire the existing attribute value and create a new one with the bad value.

        We must not SET the value on the existing vertex because AttributeValueIndexed vertices
        are shared (via MERGE), so mutating one would corrupt other attributes pointing to it.
        """
        now = Timestamp().to_string()
        query = """
        MATCH (n:Node {uuid: $node_uuid})-[ha:HAS_ATTRIBUTE]->(attr:Attribute {name: $attr_name})
        WHERE ha.branch = $branch_name AND ha.to IS NULL AND ha.status = "active"
        MATCH (attr)-[hv:HAS_VALUE]->(av)
        WHERE hv.branch = $branch_name AND hv.to IS NULL AND hv.status = "active"
        SET hv.to = $now
        MERGE (new_av:AttributeValue:AttributeValueIndexed {value: $bad_value, is_default: false})
        CREATE (attr)-[:HAS_VALUE {branch: $branch_name, branch_level: hv.branch_level, status: "active", from: $now}]->(new_av)
        """
        await db.execute_query(
            query=query,
            params={
                "node_uuid": node_id,
                "attr_name": attr_name,
                "branch_name": branch_name,
                "bad_value": bad_value,
                "now": now,
            },
        )

    async def _override_attribute_on_branch(
        self, db: InfrahubDatabase, node_id: str, attr_name: str, bad_value: str, branch_name: str
    ) -> None:
        """Create a branch-level override for an attribute value.

        Use this to inject a bad value on a user branch for a node whose attribute
        was originally created on the default branch.
        """
        now = Timestamp().to_string()
        query = """
        MATCH (n:Node {uuid: $node_uuid})-[ha:HAS_ATTRIBUTE]->(attr:Attribute {name: $attr_name})
        WHERE ha.to IS NULL AND ha.status = "active"
        WITH attr
        LIMIT 1
        MERGE (new_av:AttributeValue:AttributeValueIndexed {value: $bad_value, is_default: false})
        CREATE (attr)-[:HAS_VALUE {branch: $branch_name, branch_level: 2, status: "active", from: $now}]->(new_av)
        """
        await db.execute_query(
            query=query,
            params={
                "node_uuid": node_id,
                "attr_name": attr_name,
                "branch_name": branch_name,
                "bad_value": bad_value,
                "now": now,
            },
        )

    async def test_migration_fixes_all_branches(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        loaded_schemas: SchemaBranch,
    ) -> None:
        """Create data across default, global, and user branches, run migration, verify all fixes."""

        # --- Setup: default branch nodes ---
        role = await Node.init(db=db, schema="TestRole", branch=default_branch)
        await role.new(db=db, name="spine")
        await role.save(db=db)

        good_device = await Node.init(db=db, schema="TestDevice", branch=default_branch)
        await good_device.new(db=db, name="device1", role=role)
        await good_device.save(db=db)

        bad_dl_device = await Node.init(db=db, schema="TestDevice", branch=default_branch)
        await bad_dl_device.new(db=db, name="device2", role=role)
        await bad_dl_device.save(db=db)

        bad_hfid_device1 = await Node.init(db=db, schema="TestDevice", branch=default_branch)
        await bad_hfid_device1.new(db=db, name="device3", role=role)
        await bad_hfid_device1.save(db=db)

        bad_hfid_device2 = await Node.init(db=db, schema="TestDevice", branch=default_branch)
        await bad_hfid_device2.new(db=db, name="device4", role=role)
        await bad_hfid_device2.save(db=db)

        # --- Setup: global branch node (branch-agnostic) ---
        tag = await Node.init(db=db, schema="TestTag", branch=default_branch)
        await tag.new(db=db, name="important")
        await tag.save(db=db)

        # --- Setup: user branch ---
        user_branch = await create_branch(db=db, branch_name="test-branch-059")

        # --- Verify initial correct values ---
        assert await self._get_display_label(db=db, branch=default_branch, node_id=good_device.id) == "device1 spine"
        assert await self._get_display_label(db=db, branch=default_branch, node_id=bad_dl_device.id) == "device2 spine"
        assert await self._get_display_label(db=db, branch=default_branch, node_id=tag.id) == "important"

        # --- Inject bad values ---
        # Bad display_label on default branch
        await self._set_bad_attribute_value(
            db=db,
            node_id=bad_dl_device.id,
            attr_name="display_label",
            bad_value="device2 None",
            branch_name=default_branch.name,
        )
        # Two nodes with the same bad HFID on default branch
        bad_hfid_value = '["somedevice", "None"]'
        await self._set_bad_attribute_value(
            db=db,
            node_id=bad_hfid_device1.id,
            attr_name="human_friendly_id",
            bad_value=bad_hfid_value,
            branch_name=default_branch.name,
        )
        await self._set_bad_attribute_value(
            db=db,
            node_id=bad_hfid_device2.id,
            attr_name="human_friendly_id",
            bad_value=bad_hfid_value,
            branch_name=default_branch.name,
        )
        # Bad display_label on global branch
        await self._set_bad_attribute_value(
            db=db,
            node_id=tag.id,
            attr_name="display_label",
            bad_value="None",
            branch_name=GLOBAL_BRANCH_NAME,
        )
        # Two nodes with the same bad display_label on user branch (overriding default branch values)
        bad_branch_dl = "somedevice None"
        await self._override_attribute_on_branch(
            db=db,
            node_id=good_device.id,
            attr_name="display_label",
            bad_value=bad_branch_dl,
            branch_name=user_branch.name,
        )
        await self._override_attribute_on_branch(
            db=db,
            node_id=bad_dl_device.id,
            attr_name="display_label",
            bad_value=bad_branch_dl,
            branch_name=user_branch.name,
        )

        # --- Verify bad values were injected ---
        assert await self._get_display_label(db=db, branch=default_branch, node_id=bad_dl_device.id) == "device2 None"
        assert "None" in str(await self._get_hfid(db=db, branch=default_branch, node_id=bad_hfid_device1.id))
        assert "None" in str(await self._get_hfid(db=db, branch=default_branch, node_id=bad_hfid_device2.id))
        assert await self._get_display_label(db=db, branch=default_branch, node_id=tag.id) == "None"
        assert await self._get_display_label(db=db, branch=user_branch, node_id=good_device.id) == bad_branch_dl
        assert await self._get_display_label(db=db, branch=user_branch, node_id=bad_dl_device.id) == bad_branch_dl

        # --- Run migration on default + global branches ---
        async with db.start_session() as dbs:
            migration = Migration059()
            result = await migration.execute(migration_input=MigrationInput(db=dbs))
            assert not result.errors

        # --- Verify default branch fixes ---
        # Bad display_label should be recomputed
        assert await self._get_display_label(db=db, branch=default_branch, node_id=bad_dl_device.id) == "device2 spine"
        # Both bad HFIDs should be recomputed to their correct (distinct) values
        fixed_hfid1 = await self._get_hfid(db=db, branch=default_branch, node_id=bad_hfid_device1.id)
        fixed_hfid2 = await self._get_hfid(db=db, branch=default_branch, node_id=bad_hfid_device2.id)
        assert "None" not in str(fixed_hfid1)
        assert "None" not in str(fixed_hfid2)
        assert fixed_hfid1 != fixed_hfid2, "Two different nodes should have distinct HFIDs after fix"
        # Good device should be unchanged on default branch
        assert await self._get_display_label(db=db, branch=default_branch, node_id=good_device.id) == "device1 spine"
        # Global branch tag should be fixed
        assert await self._get_display_label(db=db, branch=default_branch, node_id=tag.id) == "important"

        await user_branch.rebase(db=db)

        # --- Run migration on user branch ---
        async with db.start_session() as dbs:
            migration = Migration059()
            result = await migration.execute_against_branch(migration_input=MigrationInput(db=dbs), branch=user_branch)
            assert not result.errors

        # Both user branch display labels should be recomputed to their correct (distinct) values
        fixed_branch_dl1 = await self._get_display_label(db=db, branch=user_branch, node_id=good_device.id)
        fixed_branch_dl2 = await self._get_display_label(db=db, branch=user_branch, node_id=bad_dl_device.id)
        assert fixed_branch_dl1 == "device1 spine"
        assert fixed_branch_dl2 == "device2 spine"

        await verify_no_duplicate_paths(db=db)
