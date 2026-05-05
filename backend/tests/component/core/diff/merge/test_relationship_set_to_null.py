"""Cardinality-one relationship cleared on the source branch (set to None).

Verifies that the merge removes the relationship on both sides and that the
NodeMetadataDefaultBranchQuery surfaces the deletion's metadata for both peers.
A rollback restores the original relationship and pre-merge metadata.
"""

from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction, MetadataOptions
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.metadata.query.node_metadata import NodeMetadataDefaultBranchQuery
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.component.core.diff.get_one_node import get_one_diff_node
from tests.helpers.db_validation import verify_graph

from .conftest import get_diff_coordinator, get_diff_merger


async def test_relationship_set_to_null(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    animal_person_schema: SchemaBranch,
) -> None:
    person_main = await Node.init(db=db, schema="TestPerson")
    await person_main.new(db=db, name="Dude")
    await person_main.save(db=db, user_id="main-user-person")
    friend_main = await Node.init(db=db, schema="TestPerson")
    await friend_main.new(db=db, name="Friend")
    before_friend_create = Timestamp()
    await friend_main.save(db=db, user_id="main-user-friend")
    after_friend_create = Timestamp()
    dog_main = await Node.init(db=db, schema="TestDog")
    await dog_main.new(db=db, name="good dog", breed="mixed", owner=person_main, best_friend=friend_main)
    before_dog_create = Timestamp()
    await dog_main.save(db=db, user_id="main-user-dog")
    after_dog_create = Timestamp()

    branch2 = await create_branch(db=db, branch_name="branch2")
    dog_branch = await NodeManager.get_one(db=db, branch=branch2, id=dog_main.id)
    await dog_branch.best_friend.update(db=db, data=None, user_id="branch-user")
    await dog_branch.save(db=db, user_id="branch-user")

    diff_coordinator = await get_diff_coordinator(db=db, branch=branch2)
    enriched_diff_metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
    enriched_diff = await diff_repository.get_one(
        diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
    )
    dog_node = get_one_diff_node(diff_root=enriched_diff, node_uuid=dog_main.id)
    assert dog_node.action is DiffAction.UPDATED
    friend_node = get_one_diff_node(diff_root=enriched_diff, node_uuid=friend_main.id)
    assert friend_node.action is DiffAction.UPDATED

    diff_merger = await get_diff_merger(db=db, branch=branch2)
    merge_at = Timestamp()
    await diff_merger.merge_graph(at=merge_at)

    # Verify dog node metadata - relationship was removed, so dog should be updated
    updated_dog = await NodeManager.get_one(
        db=db, id=dog_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS, prefetch_relationships=True
    )
    best_friend_rels = await updated_dog.best_friend.get_relationships(db=db)
    assert len(best_friend_rels) == 0
    assert before_dog_create < updated_dog._get_created_at() < after_dog_create
    assert updated_dog._get_created_by() == "main-user-dog"
    assert updated_dog._get_updated_at() == merge_at
    assert updated_dog._get_updated_by() == "branch-user"

    # Verify friend node metadata - relationship was removed from their side too
    updated_friend = await NodeManager.get_one(
        db=db, id=friend_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS, prefetch_relationships=True
    )
    best_friend_rels = await updated_friend.best_friends.get_relationships(db=db)
    assert len(best_friend_rels) == 0

    assert before_friend_create < updated_friend._get_created_at() < after_friend_create
    assert updated_friend._get_created_by() == "main-user-friend"
    assert updated_friend._get_updated_at() == merge_at
    assert updated_friend._get_updated_by() == "branch-user"

    # Verify metadata on deleted relationships using NodeMetadataDefaultBranchQuery
    node_metadata_query = await NodeMetadataDefaultBranchQuery.init(
        db=db,
        branch=default_branch,
        node_uuids=[dog_main.id, friend_main.id],
    )
    await node_metadata_query.execute(db=db)
    node_metadatas = node_metadata_query.get_metadatas()
    assert len(node_metadatas) == 2

    metadata_by_uuid = {m.uuid: m for m in node_metadatas}

    # Validate dog's relationship to friend (deleted)
    dog_meta = metadata_by_uuid[dog_main.id]
    assert dog_meta.is_deleted is False
    dog_rels_to_friend = [r for r in dog_meta.relationships if r.peer_uuid == friend_main.id]
    assert len(dog_rels_to_friend) == 1
    dog_rel_to_friend = dog_rels_to_friend[0]
    assert dog_rel_to_friend.is_deleted is True
    assert before_dog_create < dog_rel_to_friend.created_at < after_dog_create
    assert dog_rel_to_friend.created_by == "main-user-dog"
    assert dog_rel_to_friend.updated_at == merge_at
    assert dog_rel_to_friend.updated_by == "branch-user"

    # Validate friend's relationship to dog (deleted)
    friend_meta = metadata_by_uuid[friend_main.id]
    assert friend_meta.is_deleted is False
    friend_rels_to_dog = [r for r in friend_meta.relationships if r.peer_uuid == dog_main.id]
    assert len(friend_rels_to_dog) == 1
    friend_rel_to_dog = friend_rels_to_dog[0]
    assert friend_rel_to_dog.is_deleted is True
    assert before_dog_create < friend_rel_to_dog.created_at < after_dog_create
    assert friend_rel_to_dog.created_by == "main-user-dog"
    assert friend_rel_to_dog.updated_at == merge_at
    assert friend_rel_to_dog.updated_by == "branch-user"

    await verify_graph(db=db)

    # Rollback the merge
    await diff_merger.rollback(at=merge_at)

    # Verify dog metadata after rollback
    rolled_back_dog = await NodeManager.get_one(
        db=db, id=dog_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS, prefetch_relationships=True
    )
    # Dog's best_friend relationship should be restored
    rolled_back_best_friend_rels = await rolled_back_dog.best_friend.get_relationships(db=db)
    assert len(rolled_back_best_friend_rels) == 1
    assert rolled_back_best_friend_rels[0].peer_id == friend_main.id
    # Dog Node metadata should be restored to pre-merge state
    assert before_dog_create < rolled_back_dog._get_updated_at() < after_dog_create
    assert rolled_back_dog._get_updated_by() == "main-user-dog"

    # Verify friend metadata after rollback
    rolled_back_friend = await NodeManager.get_one(
        db=db, id=friend_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS, prefetch_relationships=True
    )
    # Friend's best_friends relationship should be restored
    rolled_back_best_friends_rels = await rolled_back_friend.best_friends.get_relationships(db=db)
    assert len(rolled_back_best_friends_rels) == 1
    assert rolled_back_best_friends_rels[0].peer_id == dog_main.id
    # Friend Node metadata should be restored to pre-merge state
    assert before_friend_create < rolled_back_friend._get_created_at() < after_friend_create
    assert rolled_back_friend._get_created_by() == "main-user-friend"
    assert before_friend_create < rolled_back_friend._get_updated_at() < after_friend_create
    assert rolled_back_friend._get_updated_by() == "main-user-friend"

    await verify_graph(db=db)
