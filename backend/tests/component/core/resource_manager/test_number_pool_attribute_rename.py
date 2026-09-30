"""Renaming a pool-tracked attribute must not disturb the reservation behind it.

A schema rename rebuilds the attribute vertex and copies every edge across onto the renaming branch.
The pool's IS_RESERVED edge is written on the global branch whatever the attribute's branch support,
so its copy has to stay global, and the IS_RESERVED edge on the old attribute has to stay open for every
branch that still uses the old attribute. Once no branch uses the old vertex, that edge is closed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.migrations.schema.attribute_name_update import AttributeNameUpdateMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.query.resource_manager import PoolRecordProvenance
from tests.component.core.agnostic_retirement.test_on_rebase import _rebase_branch
from tests.component.core.resource_manager.conftest import (
    SERIAL_ATTRIBUTE_NAME,
    SERIAL_POOL_START,
    delete_branch,
    pooled_widget,
    widget_schema,
)
from tests.helpers.agnostic_edges import (
    EdgeState,
    IsReservedEdge,
    attribute_edges,
    attributes_holding_only_is_reserved_edges,
    is_reserved_edge_on,
    open_active_edges,
    open_is_reserved_edge_on,
    set_open_is_reserved_edge_provenance,
)
from tests.helpers.schema.agnostic_retirement import WIDGET_KIND

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

PREVIOUS_ATTRIBUTE_NAME = SERIAL_ATTRIBUTE_NAME
NEW_ATTRIBUTE_NAME = "serial_number"


EXPECTED_AGNOSTIC_EDGES: set[tuple[str, str | None, str]] = {
    ("HAS_ATTRIBUTE", "inbound", GLOBAL_BRANCH_NAME),
    ("IS_RESERVED", "inbound", GLOBAL_BRANCH_NAME),
    ("HAS_VALUE", "outbound", GLOBAL_BRANCH_NAME),
    ("IS_PROTECTED", "outbound", GLOBAL_BRANCH_NAME),
}
"""Every edge a branch-agnostic pooled attribute carries, on the branch each is written on."""


def expected_aware_edges(branch_name: str) -> set[tuple[str, str | None, str]]:
    """The same edges when the attribute is branch-aware: only the IS_RESERVED edge stays global."""
    return {
        ("HAS_ATTRIBUTE", "inbound", branch_name),
        ("IS_RESERVED", "inbound", GLOBAL_BRANCH_NAME),
        ("HAS_VALUE", "outbound", branch_name),
        ("IS_PROTECTED", "outbound", branch_name),
    }


def _edge_summary(edges: list[EdgeState]) -> set[tuple[str, str | None, str]]:
    """Each open, active edge as what it is, which way it points, and where it sits."""
    return {(edge.edge_type, edge.direction, edge.branch) for edge in open_active_edges(edges)}


async def is_reserved_edges(db: InfrahubDatabase, pool_id: str) -> set[tuple[str, str, str, bool]]:
    """Every IS_RESERVED edge the pool holds, as the attribute name it points at, its branch, status and openness."""
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $pool_id})-[e:IS_RESERVED]->(a:Attribute)
        RETURN a.name AS name, e.branch AS branch, e.status AS status, e.to IS NULL AS is_open
        """,
        params={"pool_id": pool_id},
    )
    return {(result["name"], result["branch"], result["status"], result["is_open"]) for result in results}


BOTH_IS_RESERVED_EDGES_OPEN = {
    (PREVIOUS_ATTRIBUTE_NAME, GLOBAL_BRANCH_NAME, "active", True),
    (NEW_ATTRIBUTE_NAME, GLOBAL_BRANCH_NAME, "active", True),
}
"""A global IS_RESERVED edge on each attribute vertex, both open, and none written on a user branch."""


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
    """The same schema with the pooled attribute branch-aware, so only its IS_RESERVED edge stays global."""
    return registry.schema.register_schema(
        schema=widget_schema(serial_branch_support=BranchSupportType.AWARE), branch=default_branch.name
    )


async def test_renaming_a_pool_tracked_attribute_keeps_its_is_reserved_edge_global_and_its_number_reported(
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

    before = await attribute_edges(db=db, node_id=holder.id, attribute_name=PREVIOUS_ATTRIBUTE_NAME)
    assert _edge_summary(before) == EXPECTED_AGNOSTIC_EDGES, (
        "a branch-agnostic attribute holds its value on the global branch before the rename"
    )

    await rename_the_attribute(db=db, branch=default_branch, schema=agnostic_schema)

    after = await attribute_edges(db=db, node_id=holder.id, attribute_name=NEW_ATTRIBUTE_NAME)
    assert ("IS_RESERVED", "inbound", GLOBAL_BRANCH_NAME) in _edge_summary(after), (
        "the renamed attribute must carry the IS_RESERVED edge across on the global branch"
    )

    assert await is_reserved_edges(db=db, pool_id=serial_pool.id) == BOTH_IS_RESERVED_EDGES_OPEN, (
        "the old IS_RESERVED edge stays open because the rename leaves the old vertex's own global edges open, so it "
        "stays reachable"
    )

    serial_pool.get_attribute("node_attribute").value = NEW_ATTRIBUTE_NAME
    await serial_pool.save(db=db)

    assert await serial_pool.get_used(db=db, branch=default_branch) == [SERIAL_POOL_START], (
        "the number is still held by the renamed attribute and must stay reported as used"
    )


async def test_renaming_a_branch_aware_pooled_attribute_keeps_only_its_is_reserved_edge_global(
    db: InfrahubDatabase,
    default_branch: Branch,
    aware_schema: SchemaBranch,
    serial_pool: CoreNumberPool,
) -> None:
    """The common shape: branch-aware everywhere except the IS_RESERVED edge the pool accounts by."""
    holder = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
    await holder.new(db=db, name="holds-a-pooled-serial", serial={"from_pool": {"id": serial_pool.id}})
    await holder.save(db=db)

    assert holder.get_attribute(name=PREVIOUS_ATTRIBUTE_NAME).value == SERIAL_POOL_START
    assert await serial_pool.get_used(db=db, branch=default_branch) == [SERIAL_POOL_START]

    before = await attribute_edges(db=db, node_id=holder.id, attribute_name=PREVIOUS_ATTRIBUTE_NAME)
    assert _edge_summary(before) == expected_aware_edges(default_branch.name), (
        "a branch-aware attribute holds its value on its own branch, and only the IS_RESERVED edge is global"
    )

    await rename_the_attribute(db=db, branch=default_branch, schema=aware_schema)

    after = await attribute_edges(db=db, node_id=holder.id, attribute_name=NEW_ATTRIBUTE_NAME)
    assert _edge_summary(after) == expected_aware_edges(default_branch.name), (
        "the rename must read each edge's own branch rather than assume one for all of them"
    )

    assert await is_reserved_edges(db=db, pool_id=serial_pool.id) == {
        (PREVIOUS_ATTRIBUTE_NAME, GLOBAL_BRANCH_NAME, "active", False),
        (NEW_ATTRIBUTE_NAME, GLOBAL_BRANCH_NAME, "active", True),
    }, "no branch predates the rename, so the IS_RESERVED edge on the old attribute is closed"

    serial_pool.get_attribute("node_attribute").value = NEW_ATTRIBUTE_NAME
    await serial_pool.save(db=db)

    assert await serial_pool.get_used(db=db, branch=default_branch) == [SERIAL_POOL_START], (
        "the pool must still account for the number the renamed attribute holds"
    )


@dataclass
class BranchRenameCase:
    name: str
    serial_branch_support: BranchSupportType


BRANCH_RENAME_CASES = [
    BranchRenameCase(name="branch-aware", serial_branch_support=BranchSupportType.AWARE),
    # The attribute's own edges are global too, so closing them would erase its value on every branch.
    BranchRenameCase(name="branch-agnostic", serial_branch_support=BranchSupportType.AGNOSTIC),
]


@pytest.mark.parametrize("case", BRANCH_RENAME_CASES, ids=lambda case: case.name)
async def test_renaming_a_pooled_attribute_on_a_branch_leaves_the_default_branch_untouched(
    db: InfrahubDatabase,
    default_branch: Branch,
    serial_pool: CoreNumberPool,
    case: BranchRenameCase,
) -> None:
    registry.schema.register_schema(
        schema=widget_schema(serial_branch_support=case.serial_branch_support), branch=default_branch.name
    )
    holder = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
    await holder.new(db=db, name="holds-a-pooled-serial", serial={"from_pool": {"id": serial_pool.id}})
    await holder.save(db=db)
    assert await serial_pool.get_used(db=db, branch=default_branch) == [SERIAL_POOL_START]

    branch = await create_branch(db=db, branch_name=f"rename-{case.name}")
    await rename_the_attribute(db=db, branch=branch, schema=registry.schema.get_schema_branch(name=branch.name))

    assert await is_reserved_edges(db=db, pool_id=serial_pool.id) == BOTH_IS_RESERVED_EDGES_OPEN, (
        "the IS_RESERVED edge stays open on the attribute every other branch still uses, a global copy follows "
        "the rename, and no reservation edge is written on the renaming branch"
    )

    on_default = await registry.manager.get_one(db=db, id=holder.id, branch=default_branch, raise_on_error=True)
    assert on_default.get_attribute(name=PREVIOUS_ATTRIBUTE_NAME).value == SERIAL_POOL_START, (
        "a rename on a branch must not touch the value the default branch holds"
    )
    assert await serial_pool.get_used(db=db, branch=default_branch) == [SERIAL_POOL_START], (
        "the default branch's number must stay reported as used"
    )
    assert await serial_pool.get_free(db=db, branch=default_branch) != SERIAL_POOL_START, (
        "a rename on a branch must not offer the default branch's number again"
    )


@dataclass
class IsReservedPropertiesCase:
    name: str
    on_default_branch: bool


IS_RESERVED_PROPERTIES_CASES = [
    IsReservedPropertiesCase(name="default-branch", on_default_branch=True),
    IsReservedPropertiesCase(name="user-branch", on_default_branch=False),
]


@pytest.mark.parametrize("case", IS_RESERVED_PROPERTIES_CASES, ids=lambda case: case.name)
async def test_renaming_a_pooled_attribute_carries_every_property_of_its_is_reserved_edge(
    db: InfrahubDatabase,
    default_branch: Branch,
    aware_schema: SchemaBranch,
    serial_pool: CoreNumberPool,
    case: IsReservedPropertiesCase,
) -> None:
    """The IS_RESERVED edge says which object holds the number and how it got there; a rename must not lose either."""
    holder = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
    await holder.new(db=db, name="holds-a-pooled-serial", serial={"from_pool": {"id": serial_pool.id}})
    await holder.save(db=db)
    await set_open_is_reserved_edge_provenance(
        db=db,
        node_id=holder.id,
        attribute_name=PREVIOUS_ATTRIBUTE_NAME,
        provenance=PoolRecordProvenance.PROVIDED.value,
    )

    branch = default_branch if case.on_default_branch else await create_branch(db=db, branch_name="rename-is-reserved")
    await rename_the_attribute(db=db, branch=branch, schema=registry.schema.get_schema_branch(name=branch.name))

    renamed = await open_is_reserved_edge_on(
        db=db, pool_id=serial_pool.id, node_id=holder.id, attribute_name=NEW_ATTRIBUTE_NAME
    )
    assert renamed["identifier"] == holder.id, "the IS_RESERVED edge must still name the object that holds the number"
    assert renamed["provenance"] == PoolRecordProvenance.PROVIDED.value, (
        "the IS_RESERVED edge must still say the number was provided rather than assume the pool chose it"
    )
    assert renamed["branch"] == GLOBAL_BRANCH_NAME
    assert renamed["status"] == "active"
    assert "to" not in renamed


async def test_renaming_closes_the_old_is_reserved_edge_of_a_branch_aware_attribute(
    db: InfrahubDatabase, default_branch: Branch, serial_pool: CoreNumberPool
) -> None:
    holder = await pooled_widget(
        db=db, default_branch=default_branch, pool=serial_pool, support=BranchSupportType.AWARE
    )

    await rename_the_attribute(
        db=db, branch=default_branch, schema=registry.schema.get_schema_branch(name=default_branch.name)
    )

    assert (
        await is_reserved_edge_on(
            db=db, pool_id=serial_pool.id, node_id=holder.id, attribute_name=PREVIOUS_ATTRIBUTE_NAME
        )
        == IsReservedEdge.CLOSED
    ), "no branch reaches the old attribute vertex after the rename"
    assert (
        await is_reserved_edge_on(db=db, pool_id=serial_pool.id, node_id=holder.id, attribute_name=NEW_ATTRIBUTE_NAME)
        == IsReservedEdge.OPEN
    ), "the copy on the new vertex carries the reservation on"


async def test_an_older_branch_keeps_the_old_is_reserved_edge_open_until_it_is_deleted(
    db: InfrahubDatabase, default_branch: Branch, serial_pool: CoreNumberPool
) -> None:
    holder = await pooled_widget(
        db=db, default_branch=default_branch, pool=serial_pool, support=BranchSupportType.AWARE
    )
    older = await create_branch(db=db, branch_name="predates-the-rename")

    await rename_the_attribute(
        db=db, branch=default_branch, schema=registry.schema.get_schema_branch(name=default_branch.name)
    )

    assert (
        await is_reserved_edge_on(
            db=db, pool_id=serial_pool.id, node_id=holder.id, attribute_name=PREVIOUS_ATTRIBUTE_NAME
        )
        == IsReservedEdge.OPEN
    ), "the older branch has not taken the rename and still holds its value through the old vertex"

    await delete_branch(db=db, branch=older)

    assert (
        await is_reserved_edge_on(
            db=db, pool_id=serial_pool.id, node_id=holder.id, attribute_name=PREVIOUS_ATTRIBUTE_NAME
        )
        == IsReservedEdge.CLOSED
    ), "deleting the last branch that used the old vertex must close its IS_RESERVED edge"
    assert (
        await is_reserved_edge_on(db=db, pool_id=serial_pool.id, node_id=holder.id, attribute_name=NEW_ATTRIBUTE_NAME)
        == IsReservedEdge.OPEN
    )


async def test_the_old_is_reserved_edge_closes_once_every_older_branch_rebases_past_a_rename(
    db: InfrahubDatabase,
    default_branch: Branch,
    serial_pool: CoreNumberPool,
    dependency_provider: Provider,
) -> None:
    holder = await pooled_widget(
        db=db, default_branch=default_branch, pool=serial_pool, support=BranchSupportType.AWARE
    )
    first = await create_branch(db=db, branch_name="rebases-past-the-rename-first")
    last = await create_branch(db=db, branch_name="rebases-past-the-rename-last")

    await rename_the_attribute(
        db=db, branch=default_branch, schema=registry.schema.get_schema_branch(name=default_branch.name)
    )
    await _rebase_branch(db=db, default_branch=default_branch, branch=first, dependency_provider=dependency_provider)

    assert (
        await is_reserved_edge_on(
            db=db, pool_id=serial_pool.id, node_id=holder.id, attribute_name=PREVIOUS_ATTRIBUTE_NAME
        )
        == IsReservedEdge.OPEN
    ), "the branch not yet rebased still reads the old vertex at its fork point"

    await _rebase_branch(db=db, default_branch=default_branch, branch=last, dependency_provider=dependency_provider)

    assert (
        await is_reserved_edge_on(
            db=db, pool_id=serial_pool.id, node_id=holder.id, attribute_name=PREVIOUS_ATTRIBUTE_NAME
        )
        == IsReservedEdge.CLOSED
    ), "once the last branch reading the old vertex rebases past the rename, no branch reaches it"
    assert (
        await is_reserved_edge_on(db=db, pool_id=serial_pool.id, node_id=holder.id, attribute_name=NEW_ATTRIBUTE_NAME)
        == IsReservedEdge.OPEN
    )


@pytest.mark.parametrize("case", BRANCH_RENAME_CASES, ids=lambda case: case.name)
async def test_deleting_the_branch_that_renamed_the_attribute_deletes_the_new_is_reserved_edge(
    db: InfrahubDatabase, default_branch: Branch, serial_pool: CoreNumberPool, case: BranchRenameCase
) -> None:
    """The new attribute vertex lives only on the renaming branch, so it goes with that branch.

    Its IS_RESERVED edge is deleted with it rather than closed, and the old vertex keeps the default
    branch's open IS_RESERVED edge.
    """
    await pooled_widget(db=db, default_branch=default_branch, pool=serial_pool, support=case.serial_branch_support)
    branch = await create_branch(db=db, branch_name="renames-then-is-deleted")
    await rename_the_attribute(db=db, branch=branch, schema=registry.schema.get_schema_branch(name=branch.name))
    assert (NEW_ATTRIBUTE_NAME, GLOBAL_BRANCH_NAME, "active", True) in await is_reserved_edges(
        db=db, pool_id=serial_pool.id
    )

    await delete_branch(db=db, branch=branch)

    assert await is_reserved_edges(db=db, pool_id=serial_pool.id) == {
        (PREVIOUS_ATTRIBUTE_NAME, GLOBAL_BRANCH_NAME, "active", True)
    }, "the default branch still holds the old vertex, and the new one went with the branch"
    assert await attributes_holding_only_is_reserved_edges(db=db, pool_id=serial_pool.id) == 0, (
        "no pool may be left pointing at an attribute with nothing else linked to it"
    )
    assert await serial_pool.get_used(db=db, branch=default_branch) == [SERIAL_POOL_START]


@pytest.mark.parametrize("case", BRANCH_RENAME_CASES, ids=lambda case: case.name)
async def test_renaming_on_a_branch_keeps_the_old_is_reserved_edge_open(
    db: InfrahubDatabase, default_branch: Branch, serial_pool: CoreNumberPool, case: BranchRenameCase
) -> None:
    holder = await pooled_widget(
        db=db, default_branch=default_branch, pool=serial_pool, support=case.serial_branch_support
    )
    branch = await create_branch(db=db, branch_name="renames-on-a-branch")

    await rename_the_attribute(db=db, branch=branch, schema=registry.schema.get_schema_branch(name=branch.name))

    assert (
        await is_reserved_edge_on(
            db=db, pool_id=serial_pool.id, node_id=holder.id, attribute_name=PREVIOUS_ATTRIBUTE_NAME
        )
        == IsReservedEdge.OPEN
    ), "the default branch still holds its value through the old vertex"
