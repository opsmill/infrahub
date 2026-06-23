"""Conflict-resolved-to-base matrix test.

Stages every change type on the diff branch, layers conflicting changes on the
default branch, resolves every conflict to the base branch (diff changes
discarded), merges, and validates that the base-branch values prevailed.
Then rolls back and verifies the default branch returns to its pre-merge state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.initialization import create_branch
from infrahub.core.timestamp import Timestamp
from tests.helpers.db_validation import verify_graph

from ._conflict_setup import stage_base_conflicts
from ._matrix_setup import stage_all_change_types
from ._validators import (
    validate_all_applied_with_conflict_to_base,
    validate_rolled_back_added_node,
)
from .conftest import get_diff_coordinator, get_diff_merger

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


async def test_conflict_resolved_base(
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
    branch = await create_branch(db=db, branch_name="matrix-conflict-base")

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
    assert conflicts_map
    for conflict in conflicts_map.values():
        await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=ConflictSelection.BASE_BRANCH)

    merger = await get_diff_merger(db=db, branch=branch)
    merge_at = Timestamp()
    await merger.merge_graph(at=merge_at)

    # Base values prevailed for every conflicted change; the non-conflicting
    # added_node was still applied normally.
    await validate_all_applied_with_conflict_to_base(
        db=db,
        branch=default_branch,
        contexts=contexts,
        base_conflicts=base_conflicts,
        merge_at=merge_at,
    )
    await verify_graph(db=db)

    # After rollback the added node is gone; base-side values remain (nothing to
    # undo on base since no branch change landed there).
    await merger.rollback(at=merge_at)
    await validate_all_applied_with_conflict_to_base(
        db=db,
        branch=default_branch,
        contexts=contexts,
        base_conflicts=base_conflicts,
        merge_at=merge_at,
        added_node_state="missing",
    )
    if contexts.added_node:
        await validate_rolled_back_added_node(db=db, branch=default_branch, ctx=contexts.added_node)
    await verify_graph(db=db)
