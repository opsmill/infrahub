"""A node's non-conflicted update applies even when a related node has an unresolved conflict."""

from infrahub.core.branch import Branch
from infrahub.core.constants import MetadataOptions
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.db_validation import verify_graph

from .conftest import get_diff_coordinator, get_diff_merger


async def test_non_conflicted_node_related_to_conflicted_node(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    person_john_main: Node,
    person_jane_main: Node,
    person_alfred_main: Node,
    car_accord_main: Node,
) -> None:
    """Test that a non-conflicted node's changes merge correctly when its peer has a conflict.

    The car's owner relationship is conflicted (changed on both branches).
    The person (John) has a non-conflicted attribute update on the branch.
    After merge, John's attribute update should be on the target branch regardless
    of how the car's conflict is resolved.
    """
    branch2 = await create_branch(db=db, branch_name="branch2")

    # Create conflict on car's owner: main changes to alfred, branch changes to jane
    car_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
    await car_main.owner.update(db=db, data=person_alfred_main)
    await car_main.save(db=db, user_id="main-user")

    car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
    await car_branch.owner.update(db=db, data=person_jane_main)
    await car_branch.save(db=db, user_id="branch-user")

    # Non-conflicted change: update John's height on the branch
    person_branch = await NodeManager.get_one(db=db, branch=branch2, id=person_john_main.id)
    person_branch.height.value = 999
    await person_branch.save(db=db, user_id="branch-user-person")

    # Compute diff and resolve conflict
    diff_coordinator = await get_diff_coordinator(db=db, branch=branch2)
    enriched_diff_metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
    enriched_diff = await diff_repository.get_one(
        diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
    )
    conflicts_map = enriched_diff.get_all_conflicts()
    assert len(conflicts_map) == 1
    conflict = next(iter(conflicts_map.values()))
    await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=ConflictSelection.DIFF_BRANCH)

    # Merge
    merge_at = Timestamp()
    diff_merger = await get_diff_merger(db=db, branch=branch2)
    await diff_merger.merge_graph(at=merge_at)

    # Verify John's non-conflicted attribute update was merged
    updated_person = await NodeManager.get_one(
        db=db, id=person_john_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS
    )
    assert updated_person.height.value == 999
    assert updated_person._get_updated_at() == merge_at
    assert updated_person._get_updated_by() == "branch-user-person"

    # Verify the conflict resolution was applied (diff branch selected -> jane is owner)
    updated_car = await NodeManager.get_one(db=db, id=car_accord_main.id, prefetch_relationships=True)
    owner_rel = await updated_car.owner.get(db=db)
    assert owner_rel.peer_id == person_jane_main.id

    await verify_graph(db=db)
