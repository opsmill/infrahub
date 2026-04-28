"""Mixed conflict resolutions on a single cardinality-one relationship.

Both branches change the rel peer AND set different HAS_SOURCE on the new
rel-vertex, producing two conflicts on the same element. The tests resolve the
element conflict and the property conflict in opposite directions and verify
the merger produces a consistent graph state — verify_graph() catches any
orphan or duplicate edges.
"""

from infrahub.core.branch import Branch
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.db_validation import verify_graph

from .conftest import get_diff_coordinator, get_diff_merger


async def test_mixed_cardinality_one_element_and_property_conflicts(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    person_john_main: Node,
    person_jane_main: Node,
    person_alfred_main: Node,
    car_accord_main: Node,
    car_camry_main: Node,
) -> None:
    """Both branches change a cardinality-one rel peer AND set different HAS_SOURCE on the
    new rel-vertex. Resolve element to DIFF (jane wins), HAS_SOURCE to BASE.

    This exercises the case the merger.py TODO calls out: a source-resolved rel selection
    combined with a base-resolved property selection on the same cardinality-one element.
    With the new "close non-selected peers" approach, the merge produces a consistent
    graph state — verify_graph() catches any orphan or duplicate edges.
    """
    branch2 = await create_branch(db=db, branch_name="branch2")

    car_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
    await car_main.owner.update(db=db, data={"id": person_alfred_main.id, "_relation__source": car_camry_main.id})
    await car_main.save(db=db, user_id="main-user")

    car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
    await car_branch.owner.update(db=db, data={"id": person_jane_main.id, "_relation__source": car_accord_main.id})
    await car_branch.save(db=db, user_id="branch-user")

    diff_coordinator = await get_diff_coordinator(db=db, branch=branch2)
    enriched_diff_metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
    enriched_diff = await diff_repository.get_one(
        diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
    )
    conflicts_map = enriched_diff.get_all_conflicts()
    # element peer conflict + HAS_SOURCE property conflict
    assert len(conflicts_map) == 2

    for conflict in conflicts_map.values():
        if conflict.diff_branch_value == person_jane_main.id:
            await diff_repository.update_conflict_by_id(
                conflict_id=conflict.uuid, selection=ConflictSelection.DIFF_BRANCH
            )
        else:
            # HAS_SOURCE conflict — BASE wins
            await diff_repository.update_conflict_by_id(
                conflict_id=conflict.uuid, selection=ConflictSelection.BASE_BRANCH
            )

    merge_at = Timestamp()
    diff_merger = await get_diff_merger(db=db, branch=branch2)
    await diff_merger.merge_graph(at=merge_at)

    updated_car = await NodeManager.get_one(db=db, id=car_accord_main.id)
    owner_rel = await updated_car.owner.get(db=db)
    # Source's peer wins.
    assert owner_rel.peer_id == person_jane_main.id

    # HAS_SOURCE resolved to BASE: base's value (car_camry_main) is carried over from
    # the displaced base rel-vertex onto the selected source-side rel-vertex.
    owner_rel_source = await owner_rel.get_source(db=db)
    assert owner_rel_source is not None
    assert owner_rel_source.id == car_camry_main.id

    await verify_graph(db=db)


async def test_mixed_cardinality_one_element_base_property_diff(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    person_john_main: Node,
    person_jane_main: Node,
    person_alfred_main: Node,
    car_accord_main: Node,
    car_camry_main: Node,
) -> None:
    """Inverse of test_mixed_cardinality_one_element_and_property_conflicts: BASE element
    wins (alfred kept), DIFF property wins (source wants car_accord). The expected outcome
    is peer=alfred + HAS_SOURCE=car_accord — the user's chosen property value should land
    on the kept (base-side) rel-vertex.
    """
    branch2 = await create_branch(db=db, branch_name="branch2")

    car_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
    await car_main.owner.update(db=db, data={"id": person_alfred_main.id, "_relation__source": car_camry_main.id})
    await car_main.save(db=db, user_id="main-user")

    car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
    await car_branch.owner.update(db=db, data={"id": person_jane_main.id, "_relation__source": car_accord_main.id})
    await car_branch.save(db=db, user_id="branch-user")

    diff_coordinator = await get_diff_coordinator(db=db, branch=branch2)
    enriched_diff_metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
    enriched_diff = await diff_repository.get_one(
        diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
    )
    conflicts_map = enriched_diff.get_all_conflicts()
    assert len(conflicts_map) == 2

    for conflict in conflicts_map.values():
        if conflict.diff_branch_value == person_jane_main.id:
            # element conflict → BASE (alfred kept)
            await diff_repository.update_conflict_by_id(
                conflict_id=conflict.uuid, selection=ConflictSelection.BASE_BRANCH
            )
        else:
            # HAS_SOURCE conflict → DIFF (source's car_accord wins)
            await diff_repository.update_conflict_by_id(
                conflict_id=conflict.uuid, selection=ConflictSelection.DIFF_BRANCH
            )

    merge_at = Timestamp()
    diff_merger = await get_diff_merger(db=db, branch=branch2)
    await diff_merger.merge_graph(at=merge_at)

    updated_car = await NodeManager.get_one(db=db, id=car_accord_main.id)
    owner_rel = await updated_car.owner.get(db=db)
    # Base's peer wins.
    assert owner_rel.peer_id == person_alfred_main.id

    # HAS_SOURCE resolved to DIFF: source's value (car_accord_main) should be applied to
    # the kept base-side rel-vertex.
    owner_rel_source = await owner_rel.get_source(db=db)
    assert owner_rel_source is not None
    assert owner_rel_source.id == car_accord_main.id

    await verify_graph(db=db)


async def test_mixed_cardinality_one_element_diff_property_base_base_removed(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    person_john_main: Node,
    person_jane_main: Node,
    person_alfred_main: Node,
    car_accord_main: Node,
    car_camry_main: Node,
) -> None:
    """DIFF element wins, BASE prop wins where base's prop was REMOVED. Both branches change
    the peer; on top of that base REMOVED HAS_SOURCE while source UPDATED it. The BASE
    resolution on the property selects "removed" — source's HAS_SOURCE on the kept (source-
    side) rel must NOT be propagated, leaving no HAS_SOURCE on the kept rel.
    """
    # Initial setup on main: car has owner=alfred with source=car_camry. Both branches diverge
    # from a state with HAS_SOURCE active.
    car_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
    await car_main.owner.update(db=db, data={"id": person_alfred_main.id, "_relation__source": car_camry_main.id})
    await car_main.save(db=db, user_id="setup-user")

    branch2 = await create_branch(db=db, branch_name="branch2")

    # Main: change peer to john without setting a source — REMOVED.
    car_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
    await car_main.owner.update(db=db, data=person_john_main)
    await car_main.save(db=db, user_id="main-user")

    # Branch: change peer to jane and UPDATE source to car_accord.
    car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
    await car_branch.owner.update(db=db, data={"id": person_jane_main.id, "_relation__source": car_accord_main.id})
    await car_branch.save(db=db, user_id="branch-user")

    diff_coordinator = await get_diff_coordinator(db=db, branch=branch2)
    enriched_diff_metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
    enriched_diff = await diff_repository.get_one(
        diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
    )
    conflicts_map = enriched_diff.get_all_conflicts()
    assert len(conflicts_map) == 2

    for conflict in conflicts_map.values():
        if conflict.diff_branch_value == person_jane_main.id:
            # element conflict → DIFF (jane wins)
            await diff_repository.update_conflict_by_id(
                conflict_id=conflict.uuid, selection=ConflictSelection.DIFF_BRANCH
            )
        else:
            # HAS_SOURCE conflict → BASE (base's REMOVED wins)
            await diff_repository.update_conflict_by_id(
                conflict_id=conflict.uuid, selection=ConflictSelection.BASE_BRANCH
            )

    merge_at = Timestamp()
    diff_merger = await get_diff_merger(db=db, branch=branch2)
    await diff_merger.merge_graph(at=merge_at)

    updated_car = await NodeManager.get_one(db=db, id=car_accord_main.id)
    owner_rel = await updated_car.owner.get(db=db)
    # Source's peer wins.
    assert owner_rel.peer_id == person_jane_main.id

    # HAS_SOURCE resolved to BASE (base REMOVED): source's HAS_SOURCE on the kept rel-vertex
    # must NOT be propagated, even though source has an active edge.
    owner_rel_source = await owner_rel.get_source(db=db)
    assert owner_rel_source is None

    await verify_graph(db=db)


async def test_mixed_cardinality_one_element_base_property_diff_removed(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    person_john_main: Node,
    person_jane_main: Node,
    person_alfred_main: Node,
    car_accord_main: Node,
    car_camry_main: Node,
) -> None:
    """BASE element wins, DIFF prop wins where source's prop was REMOVED. Both branches
    change the peer; on top of that base UPDATED HAS_SOURCE while source effectively
    REMOVED it (changed peer without setting a new source). The DIFF resolution on the
    property selects "removed" — base's HAS_SOURCE on the kept rel must be closed.
    """
    # Initial setup on main: car has owner=alfred with source=car_camry. Branching from here
    # gives both branches a starting state with HAS_SOURCE active.
    car_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
    await car_main.owner.update(db=db, data={"id": person_alfred_main.id, "_relation__source": car_camry_main.id})
    await car_main.save(db=db, user_id="setup-user")

    branch2 = await create_branch(db=db, branch_name="branch2")

    # Main: change peer to john, UPDATE source to car_accord
    car_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
    await car_main.owner.update(db=db, data={"id": person_john_main.id, "_relation__source": car_accord_main.id})
    await car_main.save(db=db, user_id="main-user")

    # Branch: change peer to jane without setting a source — the new rel-vertex has no
    # HAS_SOURCE, which the cardinality-one diff enricher records as REMOVED.
    car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
    await car_branch.owner.update(db=db, data=person_jane_main)
    await car_branch.save(db=db, user_id="branch-user")

    diff_coordinator = await get_diff_coordinator(db=db, branch=branch2)
    enriched_diff_metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
    enriched_diff = await diff_repository.get_one(
        diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
    )
    conflicts_map = enriched_diff.get_all_conflicts()
    assert len(conflicts_map) == 2

    for conflict in conflicts_map.values():
        if conflict.diff_branch_value == person_jane_main.id:
            # element conflict → BASE (john kept)
            await diff_repository.update_conflict_by_id(
                conflict_id=conflict.uuid, selection=ConflictSelection.BASE_BRANCH
            )
        else:
            # HAS_SOURCE conflict → DIFF (source's REMOVED wins)
            await diff_repository.update_conflict_by_id(
                conflict_id=conflict.uuid, selection=ConflictSelection.DIFF_BRANCH
            )

    merge_at = Timestamp()
    diff_merger = await get_diff_merger(db=db, branch=branch2)
    await diff_merger.merge_graph(at=merge_at)

    updated_car = await NodeManager.get_one(db=db, id=car_accord_main.id)
    owner_rel = await updated_car.owner.get(db=db)
    # Base's peer wins.
    assert owner_rel.peer_id == person_john_main.id

    # HAS_SOURCE resolved to DIFF (source REMOVED): base's HAS_SOURCE on the kept rel-vertex
    # must be closed even though source has no edge to copy.
    owner_rel_source = await owner_rel.get_source(db=db)
    assert owner_rel_source is None

    await verify_graph(db=db)
