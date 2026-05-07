from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import ujson

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m070_normalize_mac_address_values_to_colon import Migration070
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from tests.helpers.db_validation import verify_graph
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


DEFAULT_DASH_MAC = "AA-BB-CC-DD-EE-FF"
DEFAULT_COLON_MAC = "AA:BB:CC:DD:EE:FF"
USER_DASH_MAC = "11-22-33-44-55-66"
USER_COLON_MAC = "11:22:33:44:55:66"
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
    target_branch = branch_name if branch_name is not None else registry.default_branch
    query = """
    MATCH (n:Node {uuid: $node_uuid})-[:HAS_ATTRIBUTE]->(a:Attribute {name: $attr_name})
    MATCH (a)-[hv:HAS_VALUE]->(av:AttributeValue)
    WHERE hv.status = "active" AND hv.to IS NULL AND hv.branch = $branch_name
    SET av.value = $value
    """
    await db.execute_query(
        query=query,
        params={"node_uuid": node_uuid, "attr_name": attr_name, "value": value, "branch_name": target_branch},
    )


async def _read_attribute_value(
    db: InfrahubDatabase, node_uuid: str, attr_name: str, branch_name: str | None = None
) -> str | None:
    target_branch = branch_name if branch_name is not None else registry.default_branch
    query = """
    MATCH (n:Node {uuid: $node_uuid})-[:HAS_ATTRIBUTE]->(a:Attribute {name: $attr_name})
    MATCH (a)-[hv:HAS_VALUE]->(av:AttributeValue)
    WHERE hv.status = "active" AND hv.to IS NULL AND hv.branch = $branch_name
    RETURN av.value AS value
    """
    results = await db.execute_query(
        query=query,
        params={"node_uuid": node_uuid, "attr_name": attr_name, "branch_name": target_branch},
    )
    if not results:
        return None
    return results[0]["value"]


async def _seed_dash_state_on_default(
    db: InfrahubDatabase,
    schema_kind: str,
    name: str,
    mac_dash: str,
    *,
    set_hfid: bool,
    set_display_label: str | None = None,
) -> Node:
    node = await Node.init(db=db, schema=schema_kind)
    await node.new(db=db, name=name, mac=mac_dash)
    await node.save(db=db)

    await _set_attribute_value(db=db, node_uuid=node.id, attr_name="mac", value=mac_dash)
    if set_hfid:
        await _set_attribute_value(
            db=db, node_uuid=node.id, attr_name="human_friendly_id", value=ujson.dumps([mac_dash])
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

    async def test_migration_070(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        default_iface_dl = f"{NODE_NAME} <{DEFAULT_DASH_MAC}>"
        default_iface_dl_canonical = f"{NODE_NAME} <{DEFAULT_COLON_MAC}>"
        user_iface_dl = f"{NODE_NAME} <{USER_DASH_MAC}>"
        user_iface_dl_canonical = f"{NODE_NAME} <{USER_COLON_MAC}>"

        # Default branch: TestingInterface (with HFID/display_label) and TestingStandalone (without)
        iface = await _seed_dash_state_on_default(
            db=db,
            schema_kind="TestingInterface",
            name=NODE_NAME,
            mac_dash=DEFAULT_DASH_MAC,
            set_hfid=True,
            set_display_label=default_iface_dl,
        )
        standalone = await _seed_dash_state_on_default(
            db=db,
            schema_kind="TestingStandalone",
            name="standalone-1",
            mac_dash=DEFAULT_DASH_MAC,
            set_hfid=False,
        )

        # User branch: same iface node, different MAC value (exercises branch-isolated values)
        user_branch = await create_branch(db=db, branch_name="user-branch-m070")
        branched_iface = await NodeManager.get_one(id=iface.id, db=db, branch=user_branch)
        assert branched_iface is not None
        branched_iface.mac.value = USER_COLON_MAC
        await branched_iface.save(db=db)
        await _set_attribute_value(
            db=db, node_uuid=iface.id, attr_name="mac", value=USER_DASH_MAC, branch_name=user_branch.name
        )
        await _set_attribute_value(
            db=db,
            node_uuid=iface.id,
            attr_name="human_friendly_id",
            value=ujson.dumps([USER_DASH_MAC]),
            branch_name=user_branch.name,
        )
        await _set_attribute_value(
            db=db,
            node_uuid=iface.id,
            attr_name="display_label",
            value=user_iface_dl,
            branch_name=user_branch.name,
        )

        # Run migration on default
        async with db.start_session() as dbs:
            execution_result = await Migration070().execute(migration_input=MigrationInput(db=dbs))
            assert not execution_result.errors, execution_result.errors

        # Verify default data is canonical, including standalone (no HFID/display_label)
        assert await _read_attribute_value(db=db, node_uuid=iface.id, attr_name="mac") == DEFAULT_COLON_MAC
        assert await _read_attribute_value(db=db, node_uuid=iface.id, attr_name="human_friendly_id") == ujson.dumps(
            [DEFAULT_COLON_MAC]
        )
        assert (
            await _read_attribute_value(db=db, node_uuid=iface.id, attr_name="display_label")
            == default_iface_dl_canonical
        )
        assert await _read_attribute_value(db=db, node_uuid=standalone.id, attr_name="mac") == DEFAULT_COLON_MAC

        # Rebase user branch and run migration there
        await user_branch.rebase(db=db)
        async with db.start_session() as dbs:
            result = await Migration070().execute_against_branch(
                migration_input=MigrationInput(db=dbs), branch=user_branch
            )
            assert not result.errors, result.errors

        # Verify user branch data is canonical
        assert (
            await _read_attribute_value(db=db, node_uuid=iface.id, attr_name="mac", branch_name=user_branch.name)
            == USER_COLON_MAC
        )
        assert await _read_attribute_value(
            db=db, node_uuid=iface.id, attr_name="human_friendly_id", branch_name=user_branch.name
        ) == ujson.dumps([USER_COLON_MAC])
        assert (
            await _read_attribute_value(
                db=db, node_uuid=iface.id, attr_name="display_label", branch_name=user_branch.name
            )
            == user_iface_dl_canonical
        )

        # Idempotency: re-run both migrations
        async with db.start_session() as dbs:
            assert not (await Migration070().execute(migration_input=MigrationInput(db=dbs))).errors
        async with db.start_session() as dbs:
            assert not (
                await Migration070().execute_against_branch(migration_input=MigrationInput(db=dbs), branch=user_branch)
            ).errors

        # Verify data is still canonical after the idempotent run
        assert await _read_attribute_value(db=db, node_uuid=iface.id, attr_name="mac") == DEFAULT_COLON_MAC
        assert await _read_attribute_value(db=db, node_uuid=iface.id, attr_name="human_friendly_id") == ujson.dumps(
            [DEFAULT_COLON_MAC]
        )
        assert (
            await _read_attribute_value(db=db, node_uuid=iface.id, attr_name="display_label")
            == default_iface_dl_canonical
        )
        assert await _read_attribute_value(db=db, node_uuid=standalone.id, attr_name="mac") == DEFAULT_COLON_MAC
        assert (
            await _read_attribute_value(db=db, node_uuid=iface.id, attr_name="mac", branch_name=user_branch.name)
            == USER_COLON_MAC
        )
        assert await _read_attribute_value(
            db=db, node_uuid=iface.id, attr_name="human_friendly_id", branch_name=user_branch.name
        ) == ujson.dumps([USER_COLON_MAC])
        assert (
            await _read_attribute_value(
                db=db, node_uuid=iface.id, attr_name="display_label", branch_name=user_branch.name
            )
            == user_iface_dl_canonical
        )

        await verify_graph(db=db)
