"""Clean-merge matrix test.

Stages every change type on a single diff branch, merges into the default
branch without conflicts or migrations, validates that every change landed
with the expected metadata, then rolls the merge back and verifies the
default branch returns to its pre-branch state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.initialization import create_branch
from infrahub.core.timestamp import Timestamp
from tests.helpers.db_validation import verify_graph

from ._matrix_setup import stage_all_change_types
from ._validators import validate_all_applied, validate_all_rolled_back
from .conftest import get_diff_coordinator, get_diff_merger

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


async def test_clean_merge_covers_all_change_types(
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
    branch = await create_branch(db=db, branch_name="matrix-clean")

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

    coordinator = await get_diff_coordinator(db=db, branch=branch)
    enriched_diff = await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    assert not enriched_diff.get_all_conflicts(), (
        f"clean merge should produce no conflicts; got {enriched_diff.get_all_conflicts()}"
    )

    merger = await get_diff_merger(db=db, branch=branch)
    merge_at = Timestamp()
    await merger.merge_graph(at=merge_at)

    await validate_all_applied(db=db, branch=default_branch, contexts=contexts, merge_at=merge_at)
    await verify_graph(db=db)

    await merger.rollback(at=merge_at)
    await validate_all_rolled_back(db=db, branch=default_branch, contexts=contexts)
    await verify_graph(db=db)
