"""Source-branch node-kind migration matrix test.

The diff branch runs a node-kind migration (TestCar -> Test2NewCar) before
staging every change type. When merged, the migration lands on the default
branch, all TestCar nodes become Test2NewCar, and the branch-side data changes
are applied on top.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.timestamp import Timestamp
from tests.helpers.db_validation import verify_graph

from ._matrix_setup import stage_all_change_types
from ._migrations import migrate_testcar_to_test2newcar
from ._validators import (
    validate_added_node,
    validate_added_relationship,
    validate_cleared_attribute_property,
    validate_cleared_attribute_value,
    validate_cleared_relationship_property,
    validate_deleted_node,
    validate_deleted_relationship,
    validate_rolled_back_added_node,
    validate_updated_attribute_property,
    validate_updated_attribute_value,
    validate_updated_relationship_property,
)
from .conftest import get_diff_coordinator, get_diff_merger

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


@pytest.mark.xfail(reason="to be fixed in upcoming merge refactor")
async def test_source_branch_migration(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main: Node,
    person_jane_main: Node,
    person_alfred_main: Node,
    car_accord_main: Node,
    car_camry_main: Node,
    car_yaris_main: Node,
    car_prop_cleared_main: Node,
    car_driver_main: Node,
    manufacturer_toyota_main: Node,
    car_no_manufacturer_main: Node,
    car_with_manufacturer_main: Node,
    car_tagged_main: Node,
) -> None:
    branch = await create_branch(db=db, branch_name="matrix-src-migration")

    # Ensure default branch has a registered schema before the migration runs
    # on the diff branch (otherwise the diff coordinator can't resolve main's kinds).
    main_schema = registry.schema.get_schema_branch(name=default_branch.name)
    await registry.schema.update_schema_branch(db=db, branch=default_branch, schema=main_schema, update_db=True)

    await migrate_testcar_to_test2newcar(db=db, target_branch=branch, delete_old_schema=False)

    # After migration, existing TestCar nodes are Test2NewCar on the branch.
    # Stage every change type against the migrated kind.
    contexts = await stage_all_change_types(
        db=db,
        branch=branch,
        person_john=person_john_main,
        person_jane=person_jane_main,
        person_alfred=person_alfred_main,
        car_accord=car_accord_main,
        car_camry=car_camry_main,
        car_yaris=car_yaris_main,
        car_prop_cleared=car_prop_cleared_main,
        car_driver=car_driver_main,
        manufacturer_toyota=manufacturer_toyota_main,
        car_no_manufacturer=car_no_manufacturer_main,
        car_with_manufacturer=car_with_manufacturer_main,
        car_tagged=car_tagged_main,
        added_node_kind="Test2NewCar",
    )
    # Post-merge, every car kind on main becomes Test2NewCar.
    assert contexts.added_node
    contexts.added_node.expected_kind = "Test2NewCar"
    assert contexts.deleted_node
    contexts.deleted_node.expected_kind = "Test2NewCar"

    coordinator = await get_diff_coordinator(db=db, branch=branch)
    enriched_diff = await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    assert not enriched_diff.get_all_conflicts(), (
        f"source migration should be conflict-free; got {enriched_diff.get_all_conflicts()}"
    )

    merger = await get_diff_merger(db=db, branch=branch)
    merge_at = Timestamp()
    await merger.merge_graph(at=merge_at)

    # Reload main schema so NodeManager uses the migrated kind.
    updated_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    registry.schema.set_schema_branch(name=default_branch.name, schema=updated_schema)

    await validate_added_node(db=db, branch=default_branch, ctx=contexts.added_node, merge_at=merge_at)
    await validate_deleted_node(db=db, branch=default_branch, ctx=contexts.deleted_node, merge_at=merge_at)
    for uav_ctx in contexts.updated_attribute_values:
        await validate_updated_attribute_value(db=db, branch=default_branch, ctx=uav_ctx, merge_at=merge_at)
    if contexts.cleared_attribute_value:
        await validate_cleared_attribute_value(
            db=db, branch=default_branch, ctx=contexts.cleared_attribute_value, merge_at=merge_at
        )
    for ar in contexts.added_relationships:
        await validate_added_relationship(db=db, branch=default_branch, ctx=ar, merge_at=merge_at)
    for dr in contexts.deleted_relationships:
        await validate_deleted_relationship(db=db, branch=default_branch, ctx=dr)
    for ap in contexts.updated_attribute_properties:
        await validate_updated_attribute_property(db=db, branch=default_branch, ctx=ap, merge_at=merge_at)
    for cap in contexts.cleared_attribute_properties:
        await validate_cleared_attribute_property(db=db, branch=default_branch, ctx=cap, merge_at=merge_at)
    for rp in contexts.updated_relationship_properties:
        await validate_updated_relationship_property(db=db, branch=default_branch, ctx=rp, merge_at=merge_at)
    for crp in contexts.cleared_relationship_properties:
        await validate_cleared_relationship_property(db=db, branch=default_branch, ctx=crp, merge_at=merge_at)

    await verify_graph(db=db)

    # Rollback reverts both the data changes and the migration.
    await merger.rollback(at=merge_at)

    # After rollback, schema on default_branch reverts to TestCar.
    rolled_back_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    registry.schema.set_schema_branch(name=default_branch.name, schema=rolled_back_schema)

    # added_node is gone; original cars are TestCar again.
    await validate_rolled_back_added_node(db=db, branch=default_branch, ctx=contexts.added_node)
    accord_after = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    assert accord_after is not None
    assert accord_after.get_kind() == "TestCar"
    camry_after = await NodeManager.get_one(db=db, branch=default_branch, id=car_camry_main.id)
    assert camry_after is not None
    assert camry_after.get_kind() == "TestCar"
    assert accord_after.color.value == car_accord_main.color.value

    await verify_graph(db=db)
