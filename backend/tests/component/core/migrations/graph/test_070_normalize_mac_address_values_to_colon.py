from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import ujson

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType
from infrahub.core.initialization import create_branch
from infrahub.core.migrations.graph.m070_normalize_mac_address_values_to_colon import Migration070
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


LEGACY_DASH_MAC = "AA-BB-CC-DD-EE-FF"
COLON_MAC = "AA:BB:CC:DD:EE:FF"
NODE_NAME = "eth0"


SCHEMA_ROOT = SchemaRoot(
    nodes=[
        NodeSchema(
            name="Interface",
            namespace="Testing",
            branch=BranchSupportType.AWARE,
            human_friendly_id=["mac__value"],
            display_label="{{ name__value }} <{{ mac__value }}>",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="mac", kind="MacAddress", optional=False),
            ],
        ),
        NodeSchema(
            name="Standalone",
            namespace="Testing",
            branch=BranchSupportType.AWARE,
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="mac", kind="MacAddress", optional=True),
            ],
        ),
    ],
)


async def _set_attribute_value(
    db: InfrahubDatabase, node_uuid: str, attr_name: str, value: str, branch_name: str | None = None
) -> None:
    """Rewrite a stored attribute value directly, bypassing input-time normalization."""
    branch_clause = "AND hv.branch = $branch_name" if branch_name is not None else ""
    query = f"""
    MATCH (n:Node {{uuid: $node_uuid}})-[:HAS_ATTRIBUTE]->(a:Attribute {{name: $attr_name}})
    MATCH (a)-[hv:HAS_VALUE]->(av:AttributeValue)
    WHERE hv.status = "active" AND hv.to IS NULL {branch_clause}
    SET av.value = $value
    """
    params: dict[str, Any] = {"node_uuid": node_uuid, "attr_name": attr_name, "value": value}
    if branch_name is not None:
        params["branch_name"] = branch_name
    await db.execute_query(query=query, params=params)


async def _read_attribute_value(
    db: InfrahubDatabase, node_uuid: str, attr_name: str, branch_name: str | None = None
) -> str | None:
    branch_clause = "AND hv.branch = $branch_name" if branch_name is not None else ""
    query = f"""
    MATCH (n:Node {{uuid: $node_uuid}})-[:HAS_ATTRIBUTE]->(a:Attribute {{name: $attr_name}})
    MATCH (a)-[hv:HAS_VALUE]->(av:AttributeValue)
    WHERE hv.status = "active" AND hv.to IS NULL {branch_clause}
    RETURN av.value AS value
    """
    params: dict[str, Any] = {"node_uuid": node_uuid, "attr_name": attr_name}
    if branch_name is not None:
        params["branch_name"] = branch_name
    results = await db.execute_query(query=query, params=params)
    if not results:
        return None
    return results[0]["value"]


async def _seed_legacy_dash_state(
    db: InfrahubDatabase,
    schema_kind: str,
    name: str,
    *,
    set_hfid: bool = True,
    set_display_label: str | None = None,
) -> Node:
    node = await Node.init(db=db, schema=schema_kind)
    await node.new(db=db, name=name, mac=LEGACY_DASH_MAC)
    await node.save(db=db)

    await _set_attribute_value(db=db, node_uuid=node.id, attr_name="mac", value=LEGACY_DASH_MAC)
    if set_hfid:
        await _set_attribute_value(
            db=db, node_uuid=node.id, attr_name="human_friendly_id", value=ujson.dumps([LEGACY_DASH_MAC])
        )
    if set_display_label is not None:
        await _set_attribute_value(db=db, node_uuid=node.id, attr_name="display_label", value=set_display_label)
    return node


class TestMigration070(TestInfrahubApp):
    @pytest.fixture(scope="class", autouse=True)
    async def interface_schema(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_schema: SchemaBranch
    ) -> SchemaBranch:
        return registry.schema.register_schema(schema=SCHEMA_ROOT, branch=default_branch.name)

    async def test_migration_070_rewrites_mac_value_and_dependent_fields(
        self, db: InfrahubDatabase, default_branch: Branch
    ) -> None:
        legacy_display_label = f"{NODE_NAME} <{LEGACY_DASH_MAC}>"
        canonical_display_label = f"{NODE_NAME} <{COLON_MAC}>"
        node = await _seed_legacy_dash_state(
            db=db, schema_kind="TestingInterface", name=NODE_NAME, set_display_label=legacy_display_label
        )

        # `mac.value` re-normalizes on read via BaseAttribute.__init__, so the API already shows
        # colon form pre-migration; the user-visible drift is in HFID and display_label.
        assert await _read_attribute_value(db=db, node_uuid=node.id, attr_name="mac") == LEGACY_DASH_MAC
        assert await _read_attribute_value(db=db, node_uuid=node.id, attr_name="human_friendly_id") == ujson.dumps(
            [LEGACY_DASH_MAC]
        )
        assert await _read_attribute_value(db=db, node_uuid=node.id, attr_name="display_label") == legacy_display_label

        async with db.start_session() as dbs:
            migration = Migration070()
            execution_result = await migration.execute(migration_input=MigrationInput(db=dbs))
            assert not execution_result.errors, execution_result.errors
            validation_result = await migration.validate_migration(db=dbs)
            assert not validation_result.errors, validation_result.errors

        assert await _read_attribute_value(db=db, node_uuid=node.id, attr_name="mac") == COLON_MAC
        assert await _read_attribute_value(db=db, node_uuid=node.id, attr_name="human_friendly_id") == ujson.dumps(
            [COLON_MAC]
        )
        assert (
            await _read_attribute_value(db=db, node_uuid=node.id, attr_name="display_label") == canonical_display_label
        )

    async def test_migration_070_converts_mac_when_not_in_hfid_or_display_label(
        self, db: InfrahubDatabase, default_branch: Branch
    ) -> None:
        node = await _seed_legacy_dash_state(
            db=db, schema_kind="TestingStandalone", name="standalone-1", set_hfid=False
        )

        async with db.start_session() as dbs:
            result = await Migration070().execute(migration_input=MigrationInput(db=dbs))
            assert not result.errors

        assert await _read_attribute_value(db=db, node_uuid=node.id, attr_name="mac") == COLON_MAC

    async def test_migration_070_idempotent(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        node = await _seed_legacy_dash_state(
            db=db,
            schema_kind="TestingInterface",
            name=f"{NODE_NAME}-idem",
            set_display_label=f"{NODE_NAME}-idem <{LEGACY_DASH_MAC}>",
        )

        async with db.start_session() as dbs:
            await Migration070().execute(migration_input=MigrationInput(db=dbs))

        first_mac = await _read_attribute_value(db=db, node_uuid=node.id, attr_name="mac")
        first_hfid = await _read_attribute_value(db=db, node_uuid=node.id, attr_name="human_friendly_id")

        async with db.start_session() as dbs:
            result = await Migration070().execute(migration_input=MigrationInput(db=dbs))
            assert not result.errors

        second_mac = await _read_attribute_value(db=db, node_uuid=node.id, attr_name="mac")
        second_hfid = await _read_attribute_value(db=db, node_uuid=node.id, attr_name="human_friendly_id")

        assert first_mac == second_mac == COLON_MAC
        assert first_hfid == second_hfid == ujson.dumps([COLON_MAC])

    async def test_migration_070_validate_flags_non_canonical_value(
        self, db: InfrahubDatabase, default_branch: Branch
    ) -> None:
        node = await _seed_legacy_dash_state(
            db=db,
            schema_kind="TestingInterface",
            name=f"{NODE_NAME}-validate",
            set_display_label=f"{NODE_NAME}-validate <{LEGACY_DASH_MAC}>",
        )

        async with db.start_session() as dbs:
            migration = Migration070()
            await migration.execute(migration_input=MigrationInput(db=dbs))
            clean_result = await migration.validate_migration(db=dbs)
            assert not clean_result.errors, clean_result.errors

        await _set_attribute_value(db=db, node_uuid=node.id, attr_name="mac", value=LEGACY_DASH_MAC)

        async with db.start_session() as dbs:
            corrupted_result = await Migration070().validate_migration(db=dbs)

        assert corrupted_result.errors
        assert any(node.id in err and LEGACY_DASH_MAC in err for err in corrupted_result.errors)

    async def test_migration_070_execute_against_branch(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        test_branch = await create_branch(db=db, branch_name="test-branch-m070")

        node_name = f"{NODE_NAME}-branch"
        legacy_display_label = f"{node_name} <{LEGACY_DASH_MAC}>"
        canonical_display_label = f"{node_name} <{COLON_MAC}>"

        node = await Node.init(db=db, schema="TestingInterface", branch=test_branch)
        await node.new(db=db, name=node_name, mac=LEGACY_DASH_MAC)
        await node.save(db=db)

        await _set_attribute_value(
            db=db, node_uuid=node.id, attr_name="mac", value=LEGACY_DASH_MAC, branch_name=test_branch.name
        )
        await _set_attribute_value(
            db=db,
            node_uuid=node.id,
            attr_name="human_friendly_id",
            value=ujson.dumps([LEGACY_DASH_MAC]),
            branch_name=test_branch.name,
        )
        await _set_attribute_value(
            db=db,
            node_uuid=node.id,
            attr_name="display_label",
            value=legacy_display_label,
            branch_name=test_branch.name,
        )

        # execute_against_branch requires the migration to have run on the default branch first.
        async with db.start_session() as dbs:
            await Migration070().execute(migration_input=MigrationInput(db=dbs))

        await test_branch.rebase(db=db)

        async with db.start_session() as dbs:
            result = await Migration070().execute_against_branch(
                migration_input=MigrationInput(db=dbs), branch=test_branch
            )
            assert not result.errors, result.errors

        assert (
            await _read_attribute_value(db=db, node_uuid=node.id, attr_name="mac", branch_name=test_branch.name)
            == COLON_MAC
        )
        assert await _read_attribute_value(
            db=db, node_uuid=node.id, attr_name="human_friendly_id", branch_name=test_branch.name
        ) == ujson.dumps([COLON_MAC])
        assert (
            await _read_attribute_value(
                db=db, node_uuid=node.id, attr_name="display_label", branch_name=test_branch.name
            )
            == canonical_display_label
        )
