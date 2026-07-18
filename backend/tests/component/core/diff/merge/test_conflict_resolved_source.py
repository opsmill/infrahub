"""Conflict-resolved-to-source matrix test.

Stages every change type on the diff branch, layers conflicting changes on the
default branch, resolves every conflict to the diff (source) branch, merges,
and validates that the diff-branch values prevailed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.timestamp import Timestamp
from tests.helpers.db_validation import verify_graph

from ._conflict_setup import stage_base_conflicts
from ._matrix_setup import stage_all_change_types
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
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


async def test_conflict_resolved_source(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    person_john_main: Node,
    person_jane_main: Node,
    person_alfred_main: Node,
    car_accord_main: Node,
    car_camry_main: Node,
    car_yaris_main: Node,
    car_prop_cleared_main: Node,
    car_driver_main: Node,
    manufacturer_toyota_main: Node,
    manufacturer_honda_main: Node,
    car_no_manufacturer_main: Node,
    car_with_manufacturer_main: Node,
    car_tagged_main: Node,
) -> None:
    branch = await create_branch(db=db, branch_name="matrix-conflict-src")

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
    )

    base_conflicts = await stage_base_conflicts(
        db=db,
        default_branch=default_branch,
        contexts=contexts,
        conflict_peer_node=person_john_main,
        base_user="base-conflict-user",
        conflict_peer_overrides={"manufacturer": manufacturer_honda_main},
    )

    coordinator = await get_diff_coordinator(db=db, branch=branch)
    enriched_diff = await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    conflicts_map = enriched_diff.get_all_conflicts()
    assert conflicts_map, "stage_base_conflicts should produce at least one conflict"
    for conflict in conflicts_map.values():
        await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=ConflictSelection.DIFF_BRANCH)

    merger = await get_diff_merger(db=db, branch=branch)
    merge_at = Timestamp()
    await merger.merge_graph(at=merge_at)

    # Post-merge: branch values prevail for every change type we staged.
    assert contexts.added_node
    await validate_added_node(db=db, branch=default_branch, ctx=contexts.added_node, merge_at=merge_at)

    assert contexts.deleted_node
    await validate_deleted_node(db=db, branch=default_branch, ctx=contexts.deleted_node, merge_at=merge_at)

    assert contexts.updated_attribute_values
    for uav_ctx in contexts.updated_attribute_values:
        await validate_updated_attribute_value(db=db, branch=default_branch, ctx=uav_ctx, merge_at=merge_at)

    assert contexts.cleared_attribute_value
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

    # Rollback: the added node is absent again. Base-side conflict values remain
    # on main — the base branch had them before the merge, and rollback only
    # undoes the merge itself.
    await merger.rollback(at=merge_at)
    if contexts.added_node:
        await validate_rolled_back_added_node(db=db, branch=default_branch, ctx=contexts.added_node)
    for uav_ctx in contexts.updated_attribute_values:
        base_val = base_conflicts.updated_attribute_value_base.get((uav_ctx.node_id, uav_ctx.attribute_name))
        if base_val is None:
            continue
        node = await NodeManager.get_one(db=db, branch=default_branch, id=uav_ctx.node_id)
        assert node.get_attribute(uav_ctx.attribute_name).value == base_val
    if contexts.deleted_node and base_conflicts.deleted_node_base_update:
        node = await NodeManager.get_one(db=db, branch=default_branch, id=contexts.deleted_node.node_id)
        assert node is not None
    await verify_graph(db=db)
