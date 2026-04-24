"""Target-branch node-kind migration matrix test.

After the diff branch is forked (and while it still sees ``TestCar``), the
default (target/base) branch runs a node-kind migration that renames
``TestCar`` to ``Test2NewCar``. The diff branch then stages every change type
and merges; the merge applies the branch-side changes to the migrated
``Test2NewCar`` nodes on the default branch.

For ``added_node`` specifically, the merger preserves the source-branch kind:
the new node lands on target as ``TestCar``. Converting it to ``Test2NewCar``
is the job of a follow-up schema migration in the merge pipeline (see
``backend/infrahub/core/branch/tasks.py``) and is out of scope for this
merge-only test — so the test validates that the new node is present with
``TestCar`` labels via a direct graph query, bypassing the standard validator
that goes through ``NodeManager.get_one`` (which requires a schema lookup).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.initialization import create_branch
from infrahub.core.timestamp import Timestamp
from tests.helpers.db_validation import verify_graph

from ._matrix_setup import stage_all_change_types
from ._migrations import migrate_testcar_to_test2newcar
from ._validators import validate_all_applied, validate_all_rolled_back
from .conftest import get_diff_coordinator, get_diff_merger

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


@pytest.mark.xfail(reason="to be fixed in upcoming merge refactor")
async def test_target_branch_migration(
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
    # Fork the diff branch while the schema is still TestCar.
    branch = await create_branch(db=db, branch_name="matrix-tgt-migration")

    # Now migrate TestCar -> Test2NewCar on the default (target) branch only.
    await migrate_testcar_to_test2newcar(db=db, target_branch=default_branch, delete_old_schema=True)

    # Stage every change type on the diff branch (still sees TestCar).
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
    # Existing cars on default have the migrated kind after the merge applies
    # branch-side changes to the post-migration sibling vertices.
    assert contexts.deleted_node
    contexts.deleted_node.expected_kind = "Test2NewCar"
    # The added node lands on target with its source-branch ``TestCar`` kind;
    # converting it to ``Test2NewCar`` is a schema-migration concern, not a
    # merge concern. Suppress the standard added-node validator (which would
    # need a TestCar schema on target to resolve the node via NodeManager) and
    # verify the TestCar labels directly against the graph below.
    assert contexts.added_node
    added_node_ctx = contexts.added_node
    contexts.added_node = None

    coordinator = await get_diff_coordinator(db=db, branch=branch)
    await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    merger = await get_diff_merger(db=db, branch=branch)
    merge_at = Timestamp()
    await merger.merge_graph(at=merge_at)

    await validate_all_applied(db=db, branch=default_branch, contexts=contexts, merge_at=merge_at)

    # The source-branch TestCar lands on target as TestCar (no kind translation
    # during merge — a subsequent schema migration normalizes it).
    added_node_rows = await db.execute_query(
        query="""
        MATCH (n:Node {uuid: $uuid})-[ipo:IS_PART_OF {branch: $target_branch, status: "active"}]->(:Root)
        WHERE ipo.to IS NULL
        RETURN labels(n) AS labels
        """,
        params={"uuid": added_node_ctx.node_id, "target_branch": default_branch.name},
    )
    assert len(added_node_rows) == 1, f"expected one active IS_PART_OF for added node, got {len(added_node_rows)}"
    assert "TestCar" in added_node_rows[0]["labels"], (
        f"added node's labels should still include TestCar on target (schema migration is a "
        f"separate pipeline step); got {added_node_rows[0]['labels']}"
    )

    await verify_graph(db=db)

    await merger.rollback(at=merge_at)
    await validate_all_rolled_back(db=db, branch=default_branch, contexts=contexts)
    await verify_graph(db=db)
