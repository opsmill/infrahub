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

from infrahub.core import registry
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.initialization import create_branch
from infrahub.core.ownership.fields import owner_list_value
from infrahub.core.ownership.models import NODE_HOLDER, NODE_SOURCES_HOLDER, HolderKey, HolderKind, field_holder
from infrahub.core.timestamp import Timestamp
from infrahub.database.validation import verify_graph
from tests.helpers.ownership import create_groups, read_owners, set_owners

from ._matrix_setup import stage_all_change_types
from ._migrations import migrate_testcar_to_test2newcar
from ._ownership import SET_EDGE_TYPES, count_active_holder_edges, merge, update_diff
from ._validators import validate_all_applied, validate_all_rolled_back
from .conftest import get_diff_coordinator, get_diff_merger

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


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

    await merger.rollback(merge_started_at=merge_at)
    await validate_all_rolled_back(db=db, branch=default_branch, contexts=contexts)
    await verify_graph(db=db)


@pytest.mark.parametrize(
    ("holder", "start", "end"),
    [
        pytest.param(NODE_HOLDER, None, ("dc-emea",), id="node-owner-added"),
        pytest.param(NODE_HOLDER, ("dc-emea",), None, id="node-owner-removed"),
        pytest.param(NODE_SOURCES_HOLDER, None, ("dc-emea",), id="node-source-added"),
        pytest.param("driver", None, ("dc-emea",), id="new-field-set"),
        pytest.param("color", None, ("dc-emea",), id="attribute-owner"),
    ],
)
async def test_target_branch_migration_owners(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    diff_repository: DiffRepository,
    holder: HolderKey | str,
    start: tuple[str, ...] | None,
    end: tuple[str, ...] | None,
) -> None:
    """The merge writes the owners of the branch on the vertex that the kind migration of the default branch made."""
    groups = await create_groups(db=db)
    if isinstance(holder, str):
        car_schema = registry.schema.get(name="TestCar", branch=default_branch, duplicate=False)
        field = field_holder(schema=car_schema, field_name=holder)
        assert field is not None
        holder = field
    car_id = car_accord_main.id

    def owner_ids(names: tuple[str, ...] | None) -> tuple[str, ...] | None:
        return None if names is None else tuple(sorted(groups[name] for name in names))

    if start is not None:
        await set_owners(db=db, branch=default_branch, node_id=car_id, owner_ids=owner_ids(start), holder=holder)
    branch = await create_branch(db=db, branch_name="tgt-migration-owners")
    await migrate_testcar_to_test2newcar(db=db, target_branch=default_branch, delete_old_schema=True)
    await set_owners(db=db, branch=branch, node_id=car_id, owner_ids=owner_ids(end), holder=holder)

    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    assert [node.kind for node in diff.nodes if node.uuid == car_id] == ["TestCar"]

    await merge(db=db, branch=branch)

    assert await read_owners(db=db, branch=default_branch, node_id=car_id, holder=holder) == owner_ids(end)
    assert await count_active_holder_edges(db=db, branch=default_branch, node_id=car_id) == len(end or ())
    set_edges = 1 if holder.kind is HolderKind.FIELD_SET else 0
    assert (
        await count_active_holder_edges(db=db, branch=default_branch, node_id=car_id, edge_types=SET_EDGE_TYPES)
        == set_edges
    )
    await verify_graph(db=db)


@pytest.mark.parametrize("selection", [ConflictSelection.DIFF_BRANCH, ConflictSelection.BASE_BRANCH])
@pytest.mark.parametrize(
    "holder",
    [
        pytest.param(NODE_HOLDER, id="node-owner"),
        pytest.param(NODE_SOURCES_HOLDER, id="node-source"),
        pytest.param("driver", id="field-set"),
        pytest.param("color", id="attribute-owner"),
    ],
)
async def test_target_branch_migration_owner_conflict(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    diff_repository: DiffRepository,
    holder: HolderKey | str,
    selection: ConflictSelection,
) -> None:
    """Different owner changes on the migrated default branch and on the branch conflict."""
    groups = await create_groups(db=db)
    if isinstance(holder, str):
        car_schema = registry.schema.get(name="TestCar", branch=default_branch, duplicate=False)
        field = field_holder(schema=car_schema, field_name=holder)
        assert field is not None
        holder = field
    car_id = car_accord_main.id
    branch = await create_branch(db=db, branch_name="tgt-migration-owner-conflict")
    await migrate_testcar_to_test2newcar(db=db, target_branch=default_branch, delete_old_schema=True)
    await set_owners(db=db, branch=default_branch, node_id=car_id, owner_ids=(groups["security"],), holder=holder)
    await set_owners(db=db, branch=branch, node_id=car_id, owner_ids=(groups["dc-emea"],), holder=holder)

    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    conflicts = list(diff.get_all_conflicts().values())
    assert [(conflict.base_branch_value, conflict.diff_branch_value) for conflict in conflicts] == [
        (owner_list_value((groups["security"],)), owner_list_value((groups["dc-emea"],)))
    ]
    await diff_repository.update_conflict_by_id(conflict_id=conflicts[0].uuid, selection=selection)

    await merge(db=db, branch=branch)

    merged = groups["dc-emea"] if selection is ConflictSelection.DIFF_BRANCH else groups["security"]
    assert await read_owners(db=db, branch=default_branch, node_id=car_id, holder=holder) == (merged,)
    assert await count_active_holder_edges(db=db, branch=default_branch, node_id=car_id) == 1
    await verify_graph(db=db)
