from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import ujson

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m071_recompute_hfid_for_ip_attributes import Migration071
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from tests.helpers.db_validation import verify_graph
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


DEFAULT_RAW_IP = "192.168.1.1"
DEFAULT_CANONICAL_IP = "192.168.1.1/32"
USER_RAW_IP = "10.0.0.5"
USER_CANONICAL_IP = "10.0.0.5/32"
DEFAULT_RAW_NETWORK = "10.0.0.0/255.255.255.0"
DEFAULT_CANONICAL_NETWORK = "10.0.0.0/24"
USER_RAW_NETWORK = "192.168.0.0/255.255.0.0"
USER_CANONICAL_NETWORK = "192.168.0.0/16"
DEVICE_NAME = "router-01"
NETWORK_NAME = "lan-a"


SCHEMA_ROOT = SchemaRoot(
    nodes=[
        NodeSchema(
            name="IpDevice",
            namespace="Testing",
            branch=BranchSupportType.AWARE,
            human_friendly_id=["primary_address__value"],
            display_label="{{ name__value }} <{{ primary_address__value }}>",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="primary_address", kind="IPHost", optional=False),
            ],
        ),
        NodeSchema(
            name="Network",
            namespace="Testing",
            branch=BranchSupportType.AWARE,
            human_friendly_id=["cidr__value"],
            display_label="{{ name__value }} <{{ cidr__value }}>",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="cidr", kind="IPNetwork", optional=False),
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


async def _seed_raw_state_on_default(
    db: InfrahubDatabase,
    schema_kind: str,
    attr_name: str,
    name: str,
    raw_value: str,
) -> Node:
    """Create a node and rewrite its HFID and display_label to the pre-fix raw values."""
    node = await Node.init(db=db, schema=schema_kind)
    new_kwargs: dict[str, Any] = {"name": name, attr_name: raw_value}
    await node.new(db=db, **new_kwargs)
    await node.save(db=db)
    # human_friendly_id is a List-kind attribute, stored as ujson.dumps(...) — see ListAttribute.serialize_value.
    await _set_attribute_value(
        db=db, node_uuid=node.id, attr_name="human_friendly_id", value=ujson.dumps([raw_value])
    )
    await _set_attribute_value(
        db=db, node_uuid=node.id, attr_name="display_label", value=f"{name} <{raw_value}>"
    )
    return node


class TestMigration071(TestInfrahubApp):
    @pytest.fixture(scope="class", autouse=True)
    async def normalized_kind_schema(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_schema: SchemaBranch
    ) -> SchemaBranch:
        return registry.schema.register_schema(schema=SCHEMA_ROOT, branch=default_branch.name)

    async def test_migration_071(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        default_device_dl = f"{DEVICE_NAME} <{DEFAULT_RAW_IP}>"
        default_device_dl_canonical = f"{DEVICE_NAME} <{DEFAULT_CANONICAL_IP}>"
        default_network_dl = f"{NETWORK_NAME} <{DEFAULT_RAW_NETWORK}>"
        default_network_dl_canonical = f"{NETWORK_NAME} <{DEFAULT_CANONICAL_NETWORK}>"
        user_device_dl = f"{DEVICE_NAME} <{USER_RAW_IP}>"
        user_device_dl_canonical = f"{DEVICE_NAME} <{USER_CANONICAL_IP}>"
        user_network_dl = f"{NETWORK_NAME} <{USER_RAW_NETWORK}>"
        user_network_dl_canonical = f"{NETWORK_NAME} <{USER_CANONICAL_NETWORK}>"

        # Default branch: TestingIpDevice (IPHost) and TestingNetwork (IPNetwork)
        device = await _seed_raw_state_on_default(
            db=db,
            schema_kind="TestingIpDevice",
            attr_name="primary_address",
            name=DEVICE_NAME,
            raw_value=DEFAULT_RAW_IP,
        )
        network = await _seed_raw_state_on_default(
            db=db,
            schema_kind="TestingNetwork",
            attr_name="cidr",
            name=NETWORK_NAME,
            raw_value=DEFAULT_RAW_NETWORK,
        )

        # User branch: same nodes, different IP values (exercises branch-isolated values).
        # The IP attribute is canonicalized at input time (#8896), so we save the canonical form;
        # only HFID/display_label are overwritten to the pre-fix raw form.
        user_branch = await create_branch(db=db, branch_name="user-branch-m071")
        branched_device = await NodeManager.get_one(id=device.id, db=db, branch=user_branch)
        assert branched_device is not None
        branched_device.primary_address.value = USER_CANONICAL_IP
        await branched_device.save(db=db)
        await _set_attribute_value(
            db=db,
            node_uuid=device.id,
            attr_name="human_friendly_id",
            value=ujson.dumps([USER_RAW_IP]),
            branch_name=user_branch.name,
        )
        await _set_attribute_value(
            db=db,
            node_uuid=device.id,
            attr_name="display_label",
            value=user_device_dl,
            branch_name=user_branch.name,
        )

        branched_network = await NodeManager.get_one(id=network.id, db=db, branch=user_branch)
        assert branched_network is not None
        branched_network.cidr.value = USER_CANONICAL_NETWORK
        await branched_network.save(db=db)
        await _set_attribute_value(
            db=db,
            node_uuid=network.id,
            attr_name="human_friendly_id",
            value=ujson.dumps([USER_RAW_NETWORK]),
            branch_name=user_branch.name,
        )
        await _set_attribute_value(
            db=db,
            node_uuid=network.id,
            attr_name="display_label",
            value=user_network_dl,
            branch_name=user_branch.name,
        )

        # Sanity: stored HFID/display_label are raw before migration runs
        assert await _read_attribute_value(db=db, node_uuid=device.id, attr_name="human_friendly_id") == ujson.dumps(
            [DEFAULT_RAW_IP]
        )
        assert await _read_attribute_value(db=db, node_uuid=device.id, attr_name="display_label") == default_device_dl
        assert await _read_attribute_value(db=db, node_uuid=network.id, attr_name="human_friendly_id") == ujson.dumps(
            [DEFAULT_RAW_NETWORK]
        )
        assert await _read_attribute_value(db=db, node_uuid=network.id, attr_name="display_label") == default_network_dl

        # Run migration on default
        async with db.start_session() as dbs:
            execution_result = await Migration071().execute(migration_input=MigrationInput(db=dbs))
            assert not execution_result.errors, execution_result.errors

        # Verify default data is canonical
        assert await _read_attribute_value(db=db, node_uuid=device.id, attr_name="human_friendly_id") == ujson.dumps(
            [DEFAULT_CANONICAL_IP]
        )
        assert (
            await _read_attribute_value(db=db, node_uuid=device.id, attr_name="display_label")
            == default_device_dl_canonical
        )
        assert await _read_attribute_value(db=db, node_uuid=network.id, attr_name="human_friendly_id") == ujson.dumps(
            [DEFAULT_CANONICAL_NETWORK]
        )
        assert (
            await _read_attribute_value(db=db, node_uuid=network.id, attr_name="display_label")
            == default_network_dl_canonical
        )

        # Rebase user branch and run migration there
        await user_branch.rebase(db=db)
        async with db.start_session() as dbs:
            result = await Migration071().execute_against_branch(
                migration_input=MigrationInput(db=dbs), branch=user_branch
            )
            assert not result.errors, result.errors

        # Verify user branch data is canonical
        assert await _read_attribute_value(
            db=db, node_uuid=device.id, attr_name="human_friendly_id", branch_name=user_branch.name
        ) == ujson.dumps([USER_CANONICAL_IP])
        assert (
            await _read_attribute_value(
                db=db, node_uuid=device.id, attr_name="display_label", branch_name=user_branch.name
            )
            == user_device_dl_canonical
        )
        assert await _read_attribute_value(
            db=db, node_uuid=network.id, attr_name="human_friendly_id", branch_name=user_branch.name
        ) == ujson.dumps([USER_CANONICAL_NETWORK])
        assert (
            await _read_attribute_value(
                db=db, node_uuid=network.id, attr_name="display_label", branch_name=user_branch.name
            )
            == user_network_dl_canonical
        )

        # Idempotency: re-run both migrations
        async with db.start_session() as dbs:
            assert not (await Migration071().execute(migration_input=MigrationInput(db=dbs))).errors
        async with db.start_session() as dbs:
            assert not (
                await Migration071().execute_against_branch(migration_input=MigrationInput(db=dbs), branch=user_branch)
            ).errors

        # Verify data is still canonical after the idempotent run
        assert await _read_attribute_value(db=db, node_uuid=device.id, attr_name="human_friendly_id") == ujson.dumps(
            [DEFAULT_CANONICAL_IP]
        )
        assert (
            await _read_attribute_value(db=db, node_uuid=device.id, attr_name="display_label")
            == default_device_dl_canonical
        )
        assert await _read_attribute_value(db=db, node_uuid=network.id, attr_name="human_friendly_id") == ujson.dumps(
            [DEFAULT_CANONICAL_NETWORK]
        )
        assert (
            await _read_attribute_value(db=db, node_uuid=network.id, attr_name="display_label")
            == default_network_dl_canonical
        )
        assert await _read_attribute_value(
            db=db, node_uuid=device.id, attr_name="human_friendly_id", branch_name=user_branch.name
        ) == ujson.dumps([USER_CANONICAL_IP])
        assert (
            await _read_attribute_value(
                db=db, node_uuid=device.id, attr_name="display_label", branch_name=user_branch.name
            )
            == user_device_dl_canonical
        )
        assert await _read_attribute_value(
            db=db, node_uuid=network.id, attr_name="human_friendly_id", branch_name=user_branch.name
        ) == ujson.dumps([USER_CANONICAL_NETWORK])
        assert (
            await _read_attribute_value(
                db=db, node_uuid=network.id, attr_name="display_label", branch_name=user_branch.name
            )
            == user_network_dl_canonical
        )

        await verify_graph(db=db)
