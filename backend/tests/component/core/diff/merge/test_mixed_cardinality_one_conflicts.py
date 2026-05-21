"""Mixed conflict resolutions on a single cardinality-one relationship.

Both branches change the rel peer AND set different source peers,
producing two conflicts on the same element. The tests resolve the element conflict and the
property conflict in opposite directions and verify the merger produces a consistent graph
state with expected peers and source metadata.

The tests use hierarchical relationships to ensure that same-identifier, different-direction
relationships are handled correctly.
"""

from infrahub.core.branch import Branch
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.relationship import Relationship
from infrahub.core.schema import SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.component.conftest import _build_hierarchical_location_data
from tests.helpers.db_validation import verify_graph

from .conftest import get_diff_coordinator, get_diff_merger


async def _set_parent_and_source(db: InfrahubDatabase, child: Node, parent: Node, source: Node) -> None:
    """Set the child's parent peer to `parent` and HAS_SOURCE on that rel to `source`.

    Used by tests that require an initial HAS_SOURCE state to exist before branching so that
    one side can later record the prop as REMOVED.
    """
    fresh = await NodeManager.get_one(db=db, id=child.id)
    await fresh.get_relationship("parent").update(db=db, data={"id": parent.id, "_relation__source": source.id})
    await fresh.save(db=db, user_id="setup-user")


async def _children_ids(db: InfrahubDatabase, branch: Branch, site: Node) -> set[str]:
    """Get UUIDs of the children of the given `site`"""
    fresh = await NodeManager.get_one(db=db, branch=branch, id=site.id)
    children = await fresh.get_relationship("children").get_peers(db=db)
    return set(children.keys())


async def _assert_children_rels_have_no_source(db: InfrahubDatabase, branch: Branch, site: Node) -> None:
    """For each child of the given `site`, assert that the parent relationship has no HAS_SOURCE metadata

    Need to use child.parent b/c

    """
    rels = await site.get_relationship("children").get(db=db)
    assert isinstance(rels, list)
    for rel in rels:
        assert isinstance(rel, Relationship)
        source = await rel.get_source(db=db)
        assert source is None


async def test_mixed_cardinality_one_element_and_property_conflicts(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    hierarchical_location_schema_simple: SchemaRoot,
) -> None:
    """Both branches re-parent paris to a different Region AND set a different HAS_SOURCE on the new parent.

    Resolve element to DIFF (asia), HAS_SOURCE to BASE (paris-r2).
    """
    initial = await _build_hierarchical_location_data(db=db, branch=default_branch)
    paris = initial["paris"]
    expected_children = {initial["paris-r1"].id, initial["paris-r2"].id}

    branch = await create_branch(db=db, branch_name="branch1")

    paris_main = await NodeManager.get_one(db=db, id=paris.id)
    await paris_main.get_relationship("parent").update(
        db=db, data={"id": initial["north-america"].id, "_relation__source": initial["paris-r2"].id}
    )
    await paris_main.save(db=db, user_id="main-user")

    paris_branch = await NodeManager.get_one(db=db, branch=branch, id=paris.id)
    await paris_branch.get_relationship("parent").update(
        db=db, data={"id": initial["asia"].id, "_relation__source": initial["paris-r1"].id}
    )
    await paris_branch.save(db=db, user_id="branch-user")

    diff_coordinator = await get_diff_coordinator(db=db, branch=branch)
    enriched_diff_metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    enriched_diff = await diff_repository.get_one(
        diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
    )
    conflicts_map = enriched_diff.get_all_conflicts()
    assert len(conflicts_map) == 2

    for conflict in conflicts_map.values():
        if conflict.diff_branch_value == initial["asia"].id:
            await diff_repository.update_conflict_by_id(
                conflict_id=conflict.uuid, selection=ConflictSelection.DIFF_BRANCH
            )
        else:
            await diff_repository.update_conflict_by_id(
                conflict_id=conflict.uuid, selection=ConflictSelection.BASE_BRANCH
            )

    merge_at = Timestamp()
    diff_merger = await get_diff_merger(db=db, branch=branch)
    await diff_merger.merge_graph(at=merge_at)

    paris_after = await NodeManager.get_one(db=db, id=paris.id)
    parent_rel = await paris_after.get_relationship("parent").get(db=db)
    assert parent_rel.peer_id == initial["asia"].id
    parent_source = await parent_rel.get_source(db=db)
    assert parent_source is not None
    assert parent_source.id == initial["paris-r2"].id

    assert await _children_ids(db=db, branch=default_branch, site=paris) == expected_children
    await _assert_children_rels_have_no_source(db=db, branch=default_branch, site=paris)

    await verify_graph(db=db)


async def test_mixed_cardinality_one_element_base_property_diff(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    hierarchical_location_schema_simple: SchemaRoot,
) -> None:
    """BASE element wins (north-america kept), DIFF property wins (source wants paris-r1 as HAS_SOURCE).

    The expected outcome is parent=north-america + HAS_SOURCE=paris-r1 — the user's chosen
    property value is applied to the kept rel-vertex.
    """
    initial = await _build_hierarchical_location_data(db=db, branch=default_branch)
    paris = initial["paris"]
    expected_children = {initial["paris-r1"].id, initial["paris-r2"].id}

    branch = await create_branch(db=db, branch_name="branch1")

    paris_main = await NodeManager.get_one(db=db, id=paris.id)
    await paris_main.get_relationship("parent").update(
        db=db, data={"id": initial["north-america"].id, "_relation__source": initial["paris-r2"].id}
    )
    await paris_main.save(db=db, user_id="main-user")

    paris_branch = await NodeManager.get_one(db=db, branch=branch, id=paris.id)
    await paris_branch.get_relationship("parent").update(
        db=db, data={"id": initial["asia"].id, "_relation__source": initial["paris-r1"].id}
    )
    await paris_branch.save(db=db, user_id="branch-user")

    diff_coordinator = await get_diff_coordinator(db=db, branch=branch)
    enriched_diff_metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    enriched_diff = await diff_repository.get_one(
        diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
    )
    conflicts_map = enriched_diff.get_all_conflicts()
    assert len(conflicts_map) == 2

    for conflict in conflicts_map.values():
        if conflict.diff_branch_value == initial["asia"].id:
            # element conflict → BASE (north-america kept)
            await diff_repository.update_conflict_by_id(
                conflict_id=conflict.uuid, selection=ConflictSelection.BASE_BRANCH
            )
        else:
            # HAS_SOURCE conflict → DIFF (source's paris-r1 wins)
            await diff_repository.update_conflict_by_id(
                conflict_id=conflict.uuid, selection=ConflictSelection.DIFF_BRANCH
            )

    merge_at = Timestamp()
    diff_merger = await get_diff_merger(db=db, branch=branch)
    await diff_merger.merge_graph(at=merge_at)

    paris_after = await NodeManager.get_one(db=db, id=paris.id)
    parent_rel = await paris_after.get_relationship("parent").get(db=db)
    assert parent_rel.peer_id == initial["north-america"].id
    parent_source = await parent_rel.get_source(db=db)
    assert parent_source is not None
    assert parent_source.id == initial["paris-r1"].id

    assert await _children_ids(db=db, branch=default_branch, site=paris) == expected_children
    await _assert_children_rels_have_no_source(db=db, branch=default_branch, site=paris)

    await verify_graph(db=db)


async def test_mixed_cardinality_one_element_diff_property_base_removed(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    hierarchical_location_schema_simple: SchemaRoot,
) -> None:
    """DIFF element wins, BASE prop wins where base's prop was REMOVED.

    Both branches change the parent peer; on top of that base REMOVED HAS_SOURCE while
    source UPDATED it. The BASE resolution on the property selects "removed", leaving no
    HAS_SOURCE on the kept rel.
    """
    initial = await _build_hierarchical_location_data(db=db, branch=default_branch)
    paris = initial["paris"]
    expected_children = {initial["paris-r1"].id, initial["paris-r2"].id}

    # Initial setup on main: paris.parent = europe with HAS_SOURCE = paris-r2.
    await _set_parent_and_source(db=db, child=paris, parent=initial["europe"], source=initial["paris-r2"])

    branch = await create_branch(db=db, branch_name="branch1")

    # Main: re-parent without setting source — REMOVED.
    paris_main = await NodeManager.get_one(db=db, id=paris.id)
    await paris_main.get_relationship("parent").update(db=db, data=initial["north-america"])
    await paris_main.save(db=db, user_id="main-user")

    # Branch: re-parent and UPDATE source.
    paris_branch = await NodeManager.get_one(db=db, branch=branch, id=paris.id)
    await paris_branch.get_relationship("parent").update(
        db=db, data={"id": initial["asia"].id, "_relation__source": initial["paris-r1"].id}
    )
    await paris_branch.save(db=db, user_id="branch-user")

    diff_coordinator = await get_diff_coordinator(db=db, branch=branch)
    enriched_diff_metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    enriched_diff = await diff_repository.get_one(
        diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
    )
    conflicts_map = enriched_diff.get_all_conflicts()
    assert len(conflicts_map) == 2

    for conflict in conflicts_map.values():
        if conflict.diff_branch_value == initial["asia"].id:
            # element conflict → DIFF (asia wins)
            await diff_repository.update_conflict_by_id(
                conflict_id=conflict.uuid, selection=ConflictSelection.DIFF_BRANCH
            )
        else:
            # HAS_SOURCE conflict → BASE (base's REMOVED wins)
            await diff_repository.update_conflict_by_id(
                conflict_id=conflict.uuid, selection=ConflictSelection.BASE_BRANCH
            )

    merge_at = Timestamp()
    diff_merger = await get_diff_merger(db=db, branch=branch)
    await diff_merger.merge_graph(at=merge_at)

    paris_after = await NodeManager.get_one(db=db, id=paris.id)
    parent_rel = await paris_after.get_relationship("parent").get(db=db)
    assert parent_rel.peer_id == initial["asia"].id

    # HAS_SOURCE resolved to BASE (base REMOVED)
    parent_source = await parent_rel.get_source(db=db)
    assert parent_source is None

    assert await _children_ids(db=db, branch=default_branch, site=paris) == expected_children
    await _assert_children_rels_have_no_source(db=db, branch=default_branch, site=paris)

    await verify_graph(db=db)


async def test_mixed_cardinality_one_element_base_property_diff_removed(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    hierarchical_location_schema_simple: SchemaRoot,
) -> None:
    """BASE element wins, DIFF prop wins where source's prop was REMOVED.

    Both branches change the parent peer; on top of that base UPDATED HAS_SOURCE while
    source REMOVED it. The DIFF resolution on the property selects "removed" — base's
    HAS_SOURCE on the kept rel must be closed.
    """
    initial = await _build_hierarchical_location_data(db=db, branch=default_branch)
    paris = initial["paris"]
    expected_children = {initial["paris-r1"].id, initial["paris-r2"].id}

    # Initial setup on main: paris.parent = europe with HAS_SOURCE = paris-r2.
    await _set_parent_and_source(db=db, child=paris, parent=initial["europe"], source=initial["paris-r2"])

    branch = await create_branch(db=db, branch_name="branch1")

    # Main: re-parent and UPDATE source.
    paris_main = await NodeManager.get_one(db=db, id=paris.id)
    await paris_main.get_relationship("parent").update(
        db=db, data={"id": initial["north-america"].id, "_relation__source": initial["paris-r1"].id}
    )
    await paris_main.save(db=db, user_id="main-user")

    # Branch: re-parent without setting source — REMOVED.
    paris_branch = await NodeManager.get_one(db=db, branch=branch, id=paris.id)
    await paris_branch.get_relationship("parent").update(db=db, data=initial["asia"])
    await paris_branch.save(db=db, user_id="branch-user")

    diff_coordinator = await get_diff_coordinator(db=db, branch=branch)
    enriched_diff_metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    enriched_diff = await diff_repository.get_one(
        diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
    )
    conflicts_map = enriched_diff.get_all_conflicts()
    assert len(conflicts_map) == 2

    for conflict in conflicts_map.values():
        if conflict.diff_branch_value == initial["asia"].id:
            # element conflict → BASE (north-america kept)
            await diff_repository.update_conflict_by_id(
                conflict_id=conflict.uuid, selection=ConflictSelection.BASE_BRANCH
            )
        else:
            # HAS_SOURCE conflict → DIFF (source's REMOVED wins)
            await diff_repository.update_conflict_by_id(
                conflict_id=conflict.uuid, selection=ConflictSelection.DIFF_BRANCH
            )

    merge_at = Timestamp()
    diff_merger = await get_diff_merger(db=db, branch=branch)
    await diff_merger.merge_graph(at=merge_at)

    paris_after = await NodeManager.get_one(db=db, id=paris.id)
    parent_rel = await paris_after.get_relationship("parent").get(db=db)
    assert parent_rel.peer_id == initial["north-america"].id

    # HAS_SOURCE resolved to DIFF (source REMOVED): base's HAS_SOURCE on the kept rel-vertex
    # must be closed even though source has no edge to copy.
    parent_source = await parent_rel.get_source(db=db)
    assert parent_source is None

    assert await _children_ids(db=db, branch=default_branch, site=paris) == expected_children
    await _assert_children_rels_have_no_source(db=db, branch=default_branch, site=paris)

    await verify_graph(db=db)
