"""Removing a pool-tracked attribute from the schema releases the number(s) it held."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_attribute_remove import NodeAttributeRemoveMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.timestamp import Timestamp
from tests.component.core.agnostic_retirement.support import rebase_branch
from tests.component.core.resource_manager.conftest import SERIAL_ATTRIBUTE_NAME, SERIAL_POOL_START, pooled_widget
from tests.helpers.agnostic_edges import (
    EdgeState,
    IsReservedEdge,
    is_reserved_edge_on,
    open_active_edges,
    remove_attribute_from_schema,
)
from tests.helpers.number_pool import pool_lowest_free_number, pool_used_numbers
from tests.helpers.schema.agnostic_retirement import WIDGET_KIND

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def reservation_edges(db: InfrahubDatabase, pool_id: str) -> list[EdgeState]:
    """Every reservation record the pool holds, open or closed."""
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $pool_id})-[e:IS_RESERVED]->()
        RETURN type(e) AS edge_type, e.branch AS branch, e.status AS status,
               e.from AS from_time, e.to AS to_time, e.to_user_id AS to_user_id
        """,
        params={"pool_id": pool_id},
    )
    return [EdgeState(**dict(result)) for result in results]


async def test_removing_a_pool_tracked_attribute_closes_its_record_and_frees_the_number(
    db: InfrahubDatabase,
    default_branch: Branch,
    agnostic_schema: SchemaBranch,
    serial_pool: CoreNumberPool,
) -> None:
    holder = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
    await holder.new(db=db, name="holds-a-pooled-serial", serial={"from_pool": {"id": serial_pool.id}})
    await holder.save(db=db)

    assert holder.get_attribute(name=SERIAL_ATTRIBUTE_NAME).value == SERIAL_POOL_START
    assert await pool_used_numbers(db=db, pool=serial_pool, branch=default_branch) == [SERIAL_POOL_START]

    before = await reservation_edges(db=db, pool_id=serial_pool.id)
    assert [edge.branch for edge in open_active_edges(before)] == [GLOBAL_BRANCH_NAME], (
        "the pool holds exactly one live record, on the global branch"
    )

    result = await remove_attribute_from_schema(db=db, branch=default_branch, at=Timestamp())
    assert not result.errors

    after = await reservation_edges(db=db, pool_id=serial_pool.id)
    assert open_active_edges(after) == [], "removing the attribute must close the record that described it"
    assert await pool_used_numbers(db=db, pool=serial_pool, branch=default_branch) == [], (
        "an attribute that no longer exists holds no number"
    )
    assert await pool_lowest_free_number(db=db, pool=serial_pool, branch=default_branch) == SERIAL_POOL_START, (
        "the released number is the next one the pool offers"
    )


async def test_removing_a_pooled_attribute_on_a_branch_leaves_the_default_branch_number_held(
    db: InfrahubDatabase,
    default_branch: Branch,
    agnostic_schema: SchemaBranch,
    serial_pool: CoreNumberPool,
) -> None:
    """The default branch still holds the attribute and its number, so a removal on a branch frees nothing."""
    holder = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
    await holder.new(db=db, name="holds-a-pooled-serial", serial={"from_pool": {"id": serial_pool.id}})
    await holder.save(db=db)
    assert await pool_used_numbers(db=db, pool=serial_pool, branch=default_branch) == [SERIAL_POOL_START]

    branch = await create_branch(db=db, branch_name="remove-on-a-branch")
    branch_schema = registry.schema.get_schema_branch(name=branch.name)
    previous_widget_schema = branch_schema.get(name=WIDGET_KIND)
    new_widget_schema = branch_schema.duplicate().get(name=WIDGET_KIND)
    new_widget_schema.attributes = [
        attribute for attribute in new_widget_schema.attributes if attribute.name != SERIAL_ATTRIBUTE_NAME
    ]
    migration = NodeAttributeRemoveMigration(
        previous_node_schema=previous_widget_schema,
        new_node_schema=new_widget_schema,
        schema_path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE, schema_kind=WIDGET_KIND, field_name=SERIAL_ATTRIBUTE_NAME
        ),
    )
    result = await migration.execute(migration_input=MigrationInput(db=db), branch=branch)
    assert not result.errors

    after = await reservation_edges(db=db, pool_id=serial_pool.id)
    assert [edge.branch for edge in open_active_edges(after)] == [GLOBAL_BRANCH_NAME], (
        "the record stays open for the default branch, which still holds the attribute"
    )
    on_default = await NodeManager.get_one(db=db, id=holder.id, branch=default_branch, raise_on_error=True)
    assert on_default.get_attribute(name=SERIAL_ATTRIBUTE_NAME).value == SERIAL_POOL_START
    # the branch schema in the registry still has the attribute, so it loads and the NULL value
    # proves it was closed
    on_branch = await NodeManager.get_one(db=db, id=holder.id, branch=branch, raise_on_error=True)
    assert on_branch.get_attribute(name=SERIAL_ATTRIBUTE_NAME).value is None

    assert await pool_used_numbers(db=db, pool=serial_pool, branch=default_branch) == [SERIAL_POOL_START], (
        "the default branch's number must stay reported as used"
    )
    assert await pool_lowest_free_number(db=db, pool=serial_pool, branch=default_branch) != SERIAL_POOL_START, (
        "a removal on a branch must not offer the default branch's number again"
    )


async def test_the_is_reserved_edge_closes_once_every_older_branch_rebases_past_a_removal(
    db: InfrahubDatabase,
    default_branch: Branch,
    serial_pool: CoreNumberPool,
    dependency_provider: Provider,
) -> None:
    holder = await pooled_widget(
        db=db, default_branch=default_branch, pool=serial_pool, support=BranchSupportType.AWARE
    )
    first = await create_branch(db=db, branch_name="rebases-past-the-removal-first")
    last = await create_branch(db=db, branch_name="rebases-past-the-removal-last")

    result = await remove_attribute_from_schema(db=db, branch=default_branch, at=Timestamp())
    assert not result.errors

    assert (
        await is_reserved_edge_on(
            db=db, pool_id=serial_pool.id, node_id=holder.id, attribute_name=SERIAL_ATTRIBUTE_NAME
        )
        == IsReservedEdge.OPEN
    ), "the older branches have not taken the removal and still hold the value at their fork point"

    await rebase_branch(db=db, default_branch=default_branch, branch=first, dependency_provider=dependency_provider)

    assert (
        await is_reserved_edge_on(
            db=db, pool_id=serial_pool.id, node_id=holder.id, attribute_name=SERIAL_ATTRIBUTE_NAME
        )
        == IsReservedEdge.OPEN
    ), "the branch not yet rebased still reads the attribute at its fork point"

    await rebase_branch(db=db, default_branch=default_branch, branch=last, dependency_provider=dependency_provider)

    assert (
        await is_reserved_edge_on(
            db=db, pool_id=serial_pool.id, node_id=holder.id, attribute_name=SERIAL_ATTRIBUTE_NAME
        )
        == IsReservedEdge.CLOSED
    ), "once the last branch reading the attribute rebases past the removal, no branch reaches it"
