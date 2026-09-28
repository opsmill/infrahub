"""Renaming a pool-tracked attribute must not disturb the reservation behind it.

A schema rename rebuilds the attribute vertex and copies every edge across, so the copy has to
preserve the branch each edge was written on rather than re-brand them all onto the renaming branch.
The reservation record is written on the global branch whatever the attribute's branch support, so
a branch-aware attribute has exactly one global edge among branch ones — the case that decides
whether the copy reads each edge's own branch or assumes a single one for all of them.
"""

from __future__ import annotations

import uuid
from copy import deepcopy
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType, SchemaPathType
from infrahub.core.migrations.schema.attribute_name_update import AttributeNameUpdateMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from tests.component.core.resource_manager.conftest import SERIAL_ATTRIBUTE_NAME, SERIAL_POOL_START
from tests.helpers.agnostic_edges import EdgeState, open_active_edges
from tests.helpers.schema.agnostic_retirement import AGNOSTIC_RETIREMENT_SCHEMA, WIDGET_KIND

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

PREVIOUS_ATTRIBUTE_NAME = SERIAL_ATTRIBUTE_NAME
NEW_ATTRIBUTE_NAME = "serial_number"


async def attribute_edges_on_any_branch(db: InfrahubDatabase, node_id: str, attribute_name: str) -> list[EdgeState]:
    """Every edge touching the named attribute vertex of this node, whichever branch it sits on."""
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: $attribute_name})
        WITH DISTINCT a
        MATCH (a)-[e]-()
        RETURN type(e) AS edge_type, e.branch AS branch, e.status AS status,
               e.from AS from_time, e.to AS to_time, e.to_user_id AS to_user_id,
               CASE WHEN startNode(e) = a THEN "outbound" ELSE "inbound" END AS direction
        """,
        params={"node_id": node_id, "attribute_name": attribute_name},
    )
    return [EdgeState(**dict(result)) for result in results]


EXPECTED_AGNOSTIC_EDGES: set[tuple[str, str | None, str]] = {
    ("HAS_ATTRIBUTE", "inbound", GLOBAL_BRANCH_NAME),
    ("IS_RESERVED", "inbound", GLOBAL_BRANCH_NAME),
    ("HAS_VALUE", "outbound", GLOBAL_BRANCH_NAME),
    ("IS_PROTECTED", "outbound", GLOBAL_BRANCH_NAME),
}
"""Every edge a branch-agnostic pooled attribute carries, on the branch each is written on."""


def expected_aware_edges(branch_name: str) -> set[tuple[str, str | None, str]]:
    """The same edges when the attribute is branch-aware: only the record stays global."""
    return {
        ("HAS_ATTRIBUTE", "inbound", branch_name),
        ("IS_RESERVED", "inbound", GLOBAL_BRANCH_NAME),
        ("HAS_VALUE", "outbound", branch_name),
        ("IS_PROTECTED", "outbound", branch_name),
    }


def _edge_summary(edges: list[EdgeState]) -> set[tuple[str, str | None, str]]:
    """Each open, active edge as what it is, which way it points, and where it sits."""
    return {(edge.edge_type, edge.direction, edge.branch) for edge in open_active_edges(edges)}


async def rename_the_attribute(db: InfrahubDatabase, branch: Branch, schema: SchemaBranch) -> None:
    """Run the rename migration the way a schema update would."""
    previous_widget_schema = schema.get(name=WIDGET_KIND)
    previous_attribute = previous_widget_schema.get_attribute(name=PREVIOUS_ATTRIBUTE_NAME)
    previous_attribute.id = previous_attribute.id or str(uuid.uuid4())
    new_widget_schema = schema.duplicate().get(name=WIDGET_KIND)
    new_attribute = new_widget_schema.get_attribute(name=PREVIOUS_ATTRIBUTE_NAME)
    new_attribute.name = NEW_ATTRIBUTE_NAME
    new_attribute.id = previous_attribute.id

    migration = AttributeNameUpdateMigration(
        previous_node_schema=previous_widget_schema,
        new_node_schema=new_widget_schema,
        schema_path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE, schema_kind=WIDGET_KIND, field_name=NEW_ATTRIBUTE_NAME
        ),
    )
    result = await migration.execute(migration_input=MigrationInput(db=db), branch=branch)
    assert not result.errors
    assert result.nbr_migrations_executed == 1


@pytest.fixture
async def aware_schema(db: InfrahubDatabase, default_branch: Branch) -> SchemaBranch:
    """The same schema with the pooled attribute branch-aware, so only its record stays global."""
    aware = deepcopy(AGNOSTIC_RETIREMENT_SCHEMA)
    widget = next(node for node in aware.nodes if node.kind == WIDGET_KIND)
    widget.get_attribute(name=PREVIOUS_ATTRIBUTE_NAME).branch = BranchSupportType.AWARE
    return registry.schema.register_schema(schema=aware, branch=default_branch.name)


async def test_renaming_a_pool_tracked_attribute_keeps_its_record_global_and_its_number_reported(
    db: InfrahubDatabase,
    default_branch: Branch,
    agnostic_schema: SchemaBranch,
    serial_pool: CoreNumberPool,
) -> None:
    holder = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
    await holder.new(db=db, name="holds-a-pooled-serial", serial={"from_pool": {"id": serial_pool.id}})
    await holder.save(db=db)

    assert holder.get_attribute(name=PREVIOUS_ATTRIBUTE_NAME).value == SERIAL_POOL_START
    assert await serial_pool.get_used(db=db, branch=default_branch) == [SERIAL_POOL_START]

    before = await attribute_edges_on_any_branch(db=db, node_id=holder.id, attribute_name=PREVIOUS_ATTRIBUTE_NAME)
    assert _edge_summary(before) == EXPECTED_AGNOSTIC_EDGES, (
        "a branch-agnostic attribute holds its value on the global branch before the rename"
    )

    await rename_the_attribute(db=db, branch=default_branch, schema=agnostic_schema)

    after = await attribute_edges_on_any_branch(db=db, node_id=holder.id, attribute_name=NEW_ATTRIBUTE_NAME)
    assert _edge_summary(after) == EXPECTED_AGNOSTIC_EDGES, (
        "the renamed attribute must carry every edge across on the branch it was written on"
    )

    serial_pool.get_attribute("node_attribute").value = NEW_ATTRIBUTE_NAME
    await serial_pool.save(db=db)

    assert await serial_pool.get_used(db=db, branch=default_branch) == [SERIAL_POOL_START], (
        "the number is still held by the renamed attribute and must stay reported as used"
    )


async def test_renaming_a_branch_aware_pooled_attribute_keeps_only_its_record_global(
    db: InfrahubDatabase,
    default_branch: Branch,
    aware_schema: SchemaBranch,
    serial_pool: CoreNumberPool,
) -> None:
    """The common shape: branch-aware everywhere except the record the pool accounts by."""
    holder = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
    await holder.new(db=db, name="holds-a-pooled-serial", serial={"from_pool": {"id": serial_pool.id}})
    await holder.save(db=db)

    assert holder.get_attribute(name=PREVIOUS_ATTRIBUTE_NAME).value == SERIAL_POOL_START
    assert await serial_pool.get_used(db=db, branch=default_branch) == [SERIAL_POOL_START]

    before = await attribute_edges_on_any_branch(db=db, node_id=holder.id, attribute_name=PREVIOUS_ATTRIBUTE_NAME)
    assert _edge_summary(before) == expected_aware_edges(default_branch.name), (
        "a branch-aware attribute holds its value on its own branch, and only the record is global"
    )

    await rename_the_attribute(db=db, branch=default_branch, schema=aware_schema)

    after = await attribute_edges_on_any_branch(db=db, node_id=holder.id, attribute_name=NEW_ATTRIBUTE_NAME)
    assert _edge_summary(after) == expected_aware_edges(default_branch.name), (
        "the rename must read each edge's own branch rather than assume one for all of them"
    )

    serial_pool.get_attribute("node_attribute").value = NEW_ATTRIBUTE_NAME
    await serial_pool.save(db=db)

    assert await serial_pool.get_used(db=db, branch=default_branch) == [SERIAL_POOL_START], (
        "the pool must still account for the number the renamed attribute holds"
    )
