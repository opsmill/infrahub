"""Two-step conflict resolution: a conflict is produced, then manually resolved
mid-diff by an edit on one branch, then the merge proceeds clean.

Each test stages a conflict (delete-vs-update-rel on either side), verifies the
conflict is present in the enriched diff, resolves it manually, re-runs
``update_branch_diff`` to confirm the conflict cleared, then merges and
validates the resulting metadata (including the V1/V2 relationship tracking
that survives the resolution).
"""

from infrahub.core.branch import Branch
from infrahub.core.constants import SYSTEM_USER_ID, DiffAction, MetadataOptions
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.metadata.query.node_metadata import NodeMetadataDefaultBranchQuery
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.component.core.diff.get_one_node import get_one_diff_node
from tests.helpers.db_validation import verify_graph

from .conftest import get_diff_coordinator, get_diff_merger


async def test_branch_delete_with_added_base_relationship(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    person_john_main: Node,
    person_jane_main: Node,
    person_alfred_main: Node,
    car_accord_main: Node,
    car_camry_main: Node,
) -> None:
    car_created_at = car_accord_main._get_created_at()

    branch2 = await create_branch(db=db, branch_name="branch2")
    car_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
    await car_main.owner.update(db=db, data={"id": person_alfred_main.id, "_relation__is_protected": True})
    before_alfred_update = Timestamp()
    await car_main.save(db=db, user_id="main-user")
    car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
    await car_branch.delete(db=db, user_id="branch-user")

    diff_coordinator = await get_diff_coordinator(db=db, branch=branch2)
    enriched_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
    conflicts_map = enriched_diff.get_all_conflicts()
    # check the conflict
    assert len(conflicts_map) == 1
    conflict_node = get_one_diff_node(diff_root=enriched_diff, node_uuid=car_main.id)
    assert conflict_node.conflict
    assert conflict_node.conflict.base_branch_action is DiffAction.UPDATED
    assert conflict_node.conflict.diff_branch_action is DiffAction.REMOVED

    # manually resolve the conflict
    car_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
    await car_main.owner.update(db=db, data={"id": person_john_main.id, "_relation__is_protected": False})
    before_owner_rel_resolved = Timestamp()
    await car_main.save(db=db, user_id="main-user-2")
    after_owner_rel_resolved = Timestamp()

    # check that the conflict is removed
    enriched_diff_metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
    enriched_diff = await diff_repository.get_one(
        diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
    )
    conflicts_map = enriched_diff.get_all_conflicts()
    assert len(conflicts_map) == 0

    merge_at = Timestamp()
    diff_merger = await get_diff_merger(db=db, branch=branch2)
    await diff_merger.merge_graph(at=merge_at)

    # validate that the car was deleted
    updated_car = await NodeManager.get_one(db=db, id=car_accord_main.id)
    assert updated_car is None
    # validate that the relationships were deleted
    alfred_main = await NodeManager.get_one(db=db, id=person_alfred_main.id)
    cars_rels = await alfred_main.cars.get(db=db)
    assert len(cars_rels) == 0
    john_main = await NodeManager.get_one(db=db, id=person_john_main.id)
    cars_rels = await john_main.cars.get(db=db)
    assert len(cars_rels) == 0

    # Validate metadata using NodeMetadataDefaultBranchQuery
    node_metadata_query = await NodeMetadataDefaultBranchQuery.init(
        db=db,
        branch=default_branch,
        node_uuids=[car_accord_main.id, person_john_main.id, person_alfred_main.id],
    )
    await node_metadata_query.execute(db=db)
    node_metadatas = node_metadata_query.get_metadatas()
    assert len(node_metadatas) == 3

    metadata_by_uuid = {m.uuid: m for m in node_metadatas}

    # Validate car_accord_main (deleted)
    car_meta = metadata_by_uuid[car_accord_main.id]
    assert car_meta.is_deleted is True
    assert car_meta.created_at == car_created_at
    assert car_meta.created_by == SYSTEM_USER_ID
    assert car_meta.updated_at == merge_at
    assert car_meta.updated_by == "branch-user"

    # Validate car's attributes (all deleted)
    for attr in car_meta.attributes:
        assert attr.is_deleted is True
        assert attr.created_at == car_created_at
        assert attr.created_by == SYSTEM_USER_ID
        assert attr.updated_at == merge_at
        assert attr.updated_by == "branch-user"

    # Validate car's relationship to john (deleted). Multiple Relationship
    # vertices exist between car_main and person_john_main: the original
    # fixture-created one, plus a new one created during manual conflict
    # resolution on main. Disambiguate by created_at / created_by rather
    # than relying on an ordering that can tie on updated_at.
    car_rels_to_john = [r for r in car_meta.relationships if r.peer_uuid == person_john_main.id]
    assert len(car_rels_to_john) == 2
    resolved_conflict_rel_to_john = next(r for r in car_rels_to_john if r.created_by == "main-user-2")
    assert resolved_conflict_rel_to_john.is_deleted is True
    assert before_owner_rel_resolved < resolved_conflict_rel_to_john.created_at < after_owner_rel_resolved
    assert resolved_conflict_rel_to_john.updated_by == "main-user-2"
    assert before_owner_rel_resolved < resolved_conflict_rel_to_john.updated_at < after_owner_rel_resolved
    # V1 was closed on main when main-user re-owned car to alfred — that
    # happened before the manual conflict resolution by main-user-2.
    original_rel_to_john = next(r for r in car_rels_to_john if r.created_by == SYSTEM_USER_ID)
    assert original_rel_to_john.is_deleted is True
    assert original_rel_to_john.created_at == car_created_at
    assert original_rel_to_john.updated_by == "main-user"
    assert before_alfred_update < original_rel_to_john.updated_at < before_owner_rel_resolved

    # Validate person_john_main (has deleted relationship to car)
    john_meta = metadata_by_uuid[person_john_main.id]
    assert john_meta.is_deleted is False
    # John's relationship to car should be deleted (via cascade from car deletion)
    john_rels_to_car = [r for r in john_meta.relationships if r.peer_uuid == car_accord_main.id]
    assert len(john_rels_to_car) == 2
    resolved_conflict_rel_to_car = next(r for r in john_rels_to_car if r.created_by == "main-user-2")
    assert resolved_conflict_rel_to_car.is_deleted is True
    assert before_owner_rel_resolved < resolved_conflict_rel_to_car.created_at < after_owner_rel_resolved
    assert resolved_conflict_rel_to_car.updated_by == "main-user-2"
    assert before_owner_rel_resolved < resolved_conflict_rel_to_car.updated_at < after_owner_rel_resolved
    # V1 was closed by main-user pre-conflict-resolution (see sibling rel to john above).
    original_rel_to_car = next(r for r in john_rels_to_car if r.created_by == SYSTEM_USER_ID)
    assert original_rel_to_car.is_deleted is True
    assert original_rel_to_car.created_at == car_created_at
    assert original_rel_to_car.updated_by == "main-user"
    assert before_alfred_update < original_rel_to_car.updated_at < before_owner_rel_resolved

    # Validate person_alfred_main (should have no relationship to car since it was
    # added after branch creation and then reverted before merge)
    alfred_meta = metadata_by_uuid[person_alfred_main.id]
    assert alfred_meta.is_deleted is False
    assert alfred_meta.created_by == SYSTEM_USER_ID
    assert alfred_meta.created_at < before_alfred_update
    # the car-alfred relationship is deleted by main-user-2
    assert alfred_meta.updated_by == "main-user-2"
    assert before_owner_rel_resolved < alfred_meta.updated_at < after_owner_rel_resolved

    await diff_merger.rollback(at=merge_at)

    rolled_back_car = await NodeManager.get_one(db=db, id=car_accord_main.id, include_metadata=MetadataOptions.OWNER)
    owner_rel = await rolled_back_car.owner.get(db=db)
    assert owner_rel.peer_id == person_john_main.id
    assert owner_rel.is_protected is False

    # Validate metadata after rollback - car should have metadata from before merge
    # The car was modified on main (twice: first to alfred, then back to john)
    # After rollback, the metadata should reflect the main-user-2 changes (the last main branch change)
    rolled_back_car_with_metadata = await NodeManager.get_one(
        db=db, id=car_accord_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS, prefetch_relationships=True
    )
    # The car Node metadata should reflect the main-user-2 changes since that was the last change on main
    assert rolled_back_car_with_metadata._get_created_by() == SYSTEM_USER_ID
    assert rolled_back_car_with_metadata._get_created_at() == car_created_at
    assert rolled_back_car_with_metadata._get_updated_by() == "main-user-2"
    assert before_owner_rel_resolved < rolled_back_car_with_metadata._get_updated_at() < after_owner_rel_resolved
    await verify_graph(db=db)


async def test_base_delete_with_added_branch_relationship(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    person_john_main: Node,
    person_jane_main: Node,
    person_alfred_main: Node,
    car_accord_main: Node,
    car_camry_main: Node,
) -> None:
    car_created_at = car_accord_main._get_created_at()

    branch2 = await create_branch(db=db, branch_name="branch2")
    car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
    await car_branch.owner.update(db=db, data={"id": person_alfred_main.id, "_relation__is_protected": True})
    before_branch_update = Timestamp()
    await car_branch.save(db=db, user_id="branch-user")
    car_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
    before_main_delete = Timestamp()
    await car_main.delete(db=db, user_id="main-user")
    after_main_delete = Timestamp()

    diff_coordinator = await get_diff_coordinator(db=db, branch=branch2)
    enriched_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
    conflicts_map = enriched_diff.get_all_conflicts()
    # check the conflict
    assert len(conflicts_map) == 1
    conflict_node = get_one_diff_node(diff_root=enriched_diff, node_uuid=car_branch.id)
    assert conflict_node.conflict
    assert conflict_node.conflict.base_branch_action is DiffAction.REMOVED
    assert conflict_node.conflict.diff_branch_action is DiffAction.UPDATED

    # manually resolve the conflict
    car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
    await car_branch.owner.update(db=db, data={"id": person_john_main.id, "_relation__is_protected": False})
    await car_branch.save(db=db, user_id="branch-user-2")

    # check that the conflict is removed
    enriched_diff_metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
    enriched_diff = await diff_repository.get_one(
        diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
    )
    conflicts_map = enriched_diff.get_all_conflicts()
    assert len(conflicts_map) == 0

    merge_at = Timestamp()
    diff_merger = await get_diff_merger(db=db, branch=branch2)
    await diff_merger.merge_graph(at=merge_at)

    # validate that the car remains deleted
    updated_car = await NodeManager.get_one(db=db, id=car_accord_main.id)
    assert updated_car is None
    # validate that the relationships do not exist
    alfred_main = await NodeManager.get_one(db=db, id=person_alfred_main.id)
    cars_rels = await alfred_main.cars.get(db=db)
    assert len(cars_rels) == 0
    john_main = await NodeManager.get_one(db=db, id=person_john_main.id)
    cars_rels = await john_main.cars.get(db=db)
    assert len(cars_rels) == 0

    # Validate metadata using NodeMetadataDefaultBranchQuery
    node_metadata_query = await NodeMetadataDefaultBranchQuery.init(
        db=db,
        branch=default_branch,
        node_uuids=[car_accord_main.id, person_john_main.id, person_alfred_main.id],
    )
    await node_metadata_query.execute(db=db)
    node_metadatas = node_metadata_query.get_metadatas()
    assert len(node_metadatas) == 3

    metadata_by_uuid = {m.uuid: m for m in node_metadatas}

    # Validate car_accord_main (deleted on main, remains deleted after merge)
    car_meta = metadata_by_uuid[car_accord_main.id]
    assert car_meta.is_deleted is True
    assert car_meta.created_at == car_created_at
    assert car_meta.created_by == SYSTEM_USER_ID
    # Car was deleted on main, so updated_at/by should reflect main-user's delete
    assert before_main_delete < car_meta.updated_at < after_main_delete
    assert car_meta.updated_by == "main-user"

    # Validate car's attributes (all deleted)
    for attr in car_meta.attributes:
        assert attr.is_deleted is True
        assert attr.created_at == car_created_at
        assert attr.created_by == SYSTEM_USER_ID
        assert before_main_delete < attr.updated_at < after_main_delete
        assert attr.updated_by == "main-user"

    # Validate car's relationship to john (deleted)
    # The original relationship to john was deleted when car was deleted on main
    car_rels_to_john = [r for r in car_meta.relationships if r.peer_uuid == person_john_main.id]
    assert len(car_rels_to_john) == 1
    original_rel_to_john = car_rels_to_john[0]
    assert original_rel_to_john.is_deleted is True
    assert original_rel_to_john.created_by == SYSTEM_USER_ID
    assert original_rel_to_john.created_at == car_created_at
    assert original_rel_to_john.updated_by == "main-user"
    assert before_main_delete < original_rel_to_john.updated_at < after_main_delete

    # Validate person_john_main (has deleted relationship to car)
    john_meta = metadata_by_uuid[person_john_main.id]
    assert john_meta.is_deleted is False
    # John's relationship to car should be deleted (car was deleted on main)
    john_rels_to_car = [r for r in john_meta.relationships if r.peer_uuid == car_accord_main.id]
    assert len(john_rels_to_car) == 1
    john_rel_to_car = john_rels_to_car[0]
    assert john_rel_to_car.is_deleted is True
    assert john_rel_to_car.created_by == SYSTEM_USER_ID
    assert john_rel_to_car.created_at == car_created_at
    assert john_rel_to_car.updated_by == "main-user"
    assert before_main_delete < john_rel_to_car.updated_at < after_main_delete

    # Validate person_alfred_main (should have no relationship to car since the branch
    # changes are discarded when the car remains deleted)
    alfred_meta = metadata_by_uuid[person_alfred_main.id]
    assert alfred_meta.is_deleted is False
    assert alfred_meta.created_by == SYSTEM_USER_ID
    assert alfred_meta.created_at < before_branch_update
    #  Alfred remains unchanged on main
    assert alfred_meta.updated_by == SYSTEM_USER_ID
    assert alfred_meta.updated_at < before_branch_update
    # Alfred should not have been updated by this merge since branch changes were discarded
    alfred_rels_to_car = [r for r in alfred_meta.relationships if r.peer_uuid == car_accord_main.id]
    assert len(alfred_rels_to_car) == 0

    await diff_merger.rollback(at=merge_at)

    # validate that car remains deleted after rollback (no change expected)
    rolled_back_car = await NodeManager.get_one(db=db, id=car_accord_main.id)
    assert rolled_back_car is None

    # Validate metadata after rollback - car should still be deleted with same metadata
    node_metadata_query_after_rollback = await NodeMetadataDefaultBranchQuery.init(
        db=db,
        branch=default_branch,
        node_uuids=[car_accord_main.id, person_john_main.id, person_alfred_main.id],
    )
    await node_metadata_query_after_rollback.execute(db=db)
    node_metadatas_after_rollback = node_metadata_query_after_rollback.get_metadatas()
    assert len(node_metadatas_after_rollback) == 3

    metadata_by_uuid_after_rollback = {m.uuid: m for m in node_metadatas_after_rollback}

    # Validate car metadata after rollback - should be same as after merge
    car_meta_after_rollback = metadata_by_uuid_after_rollback[car_accord_main.id]
    assert car_meta_after_rollback.is_deleted is True
    assert car_meta_after_rollback.created_at == car_created_at
    assert car_meta_after_rollback.created_by == SYSTEM_USER_ID
    assert before_main_delete < car_meta_after_rollback.updated_at < after_main_delete
    assert car_meta_after_rollback.updated_by == "main-user"

    # Validate john metadata after rollback
    john_meta_after_rollback = metadata_by_uuid_after_rollback[person_john_main.id]
    assert john_meta_after_rollback.is_deleted is False
    john_rels_to_car_after_rollback = [
        r for r in john_meta_after_rollback.relationships if r.peer_uuid == car_accord_main.id
    ]
    assert len(john_rels_to_car_after_rollback) == 1
    john_rel_to_car_after_rollback = john_rels_to_car_after_rollback[0]
    assert john_rel_to_car_after_rollback.is_deleted is True
    assert john_rel_to_car_after_rollback.updated_by == "main-user"
    assert before_main_delete < john_rel_to_car_after_rollback.updated_at < after_main_delete

    await verify_graph(db=db)
