"""Edge cases: node deletes combined with branch-side additions."""


from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.metadata.query.node_metadata import NodeMetadataDefaultBranchQuery
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.component.core.test_utils import verify_all_linked_edges_deleted
from tests.helpers.db_validation import verify_graph

from .conftest import get_diff_coordinator, get_diff_merger


async def test_base_delete_with_added_branch_attr_source(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    person_john_main: Node,
    person_alfred_main: Node,
    car_accord_main: Node,
) -> None:
    """Branch sets an attribute source (HAS_SOURCE) pointing to a Node that main deletes.
    After merge, no orphan active HAS_SOURCE should point to the deleted Node.
    """
    branch2 = await create_branch(db=db, branch_name="branch2")
    # Branch: set car.color.source = person_alfred_main (creates HAS_SOURCE on source branch)
    car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_accord_main.id)
    car_branch.color.source = person_alfred_main
    await car_branch.save(db=db, user_id="branch-user")

    # Main: delete person_alfred_main (the Node that the branch's HAS_SOURCE points to)
    alfred_main = await NodeManager.get_one(db=db, id=person_alfred_main.id)
    Timestamp()
    await alfred_main.delete(db=db, user_id="main-user")
    Timestamp()

    # Run diff coordinator and resolve any conflicts by clearing the source on branch
    diff_coordinator = await get_diff_coordinator(db=db, branch=branch2)
    enriched_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
    conflicts_map = enriched_diff.get_all_conflicts()
    if conflicts_map:
        for conflict in conflicts_map.values():
            if conflict.selected_branch is None:
                await diff_repository.update_conflict_by_id(
                    conflict_id=conflict.uuid, selection=ConflictSelection.BASE_BRANCH
                )

    merge_at = Timestamp()
    diff_merger = await get_diff_merger(db=db, branch=branch2)
    await diff_merger.merge_graph(at=merge_at)

    # Alfred remains deleted on main
    alfred_after = await NodeManager.get_one(db=db, id=person_alfred_main.id)
    assert alfred_after is None

    # No active HAS_SOURCE/HAS_OWNER on main should point to the deleted Alfred
    orphan_query = """
    MATCH (field)-[e:HAS_SOURCE|HAS_OWNER]->(target:Node {uuid: $alfred_uuid})
    WHERE e.branch = $default_branch
    AND e.status = "active"
    AND e.to IS NULL
    RETURN type(e) AS edge_type, labels(field) AS field_labels, field.name AS field_name
    """
    orphans = await db.execute_query(
        query=orphan_query,
        params={"alfred_uuid": person_alfred_main.id, "default_branch": default_branch.name},
    )
    assert len(orphans) == 0, (
        f"Found {len(orphans)} orphan HAS_SOURCE/HAS_OWNER edge(s) on main pointing to deleted Alfred: "
        f"{[(r['edge_type'], r['field_labels'], r['field_name']) for r in orphans]}"
    )

    await verify_graph(db=db)


async def test_delete_with_many_relationship_added(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot
) -> None:
    # remove TestCar relationship to TestPerson
    car_schema = car_person_schema_unregistered.get(name="TestCar")
    car_schema.relationships = []
    registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)

    # initial data - track creation timestamps
    before_person_1_create = Timestamp()
    person_1 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person_1.new(db=db, name="Alice", height=160)
    await person_1.save(db=db, user_id="setup-user")
    after_person_1_create = Timestamp()

    before_person_2_create = Timestamp()
    person_2 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person_2.new(db=db, name="Bob", height=161)
    await person_2.save(db=db, user_id="setup-user")
    after_person_2_create = Timestamp()

    before_car_1_create = Timestamp()
    car_1 = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car_1.new(db=db, name="smart", nbr_seats=2, is_electric=True)
    await car_1.save(db=db, user_id="setup-user")
    after_car_1_create = Timestamp()

    before_car_2_create = Timestamp()
    car_2 = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car_2.new(db=db, name="big", nbr_seats=12, is_electric=False)
    await car_2.save(db=db, user_id="setup-user")
    after_car_2_create = Timestamp()

    # make the branch
    branch2 = await create_branch(db=db, branch_name="branch2")

    # add relationship on main
    before_rel_create = Timestamp()
    person_1_main = await NodeManager.get_one(db=db, id=person_1.id)
    await person_1_main.cars.update(db=db, data=[car_1, car_2])
    await person_1_main.save(db=db, user_id="main-user")
    after_rel_create = Timestamp()
    # delete node on branch
    person_1_branch = await NodeManager.get_one(db=db, branch=branch2, id=person_1.id)
    await person_1_branch.delete(db=db, user_id="branch-user")

    # check that there are no conflicts
    diff_coordinator = await get_diff_coordinator(db=db, branch=branch2)
    enriched_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
    conflicts_map = enriched_diff.get_all_conflicts()
    assert len(conflicts_map) == 0

    # merge the branch
    merge_at = Timestamp()
    diff_merger = await get_diff_merger(db=db, branch=branch2)
    await diff_merger.merge_graph(at=merge_at)

    # validate that person_1 is deleted
    deleted_person = await NodeManager.get_one(db=db, id=person_1.id)
    assert deleted_person is None
    # validate that all attributes and relationships connected to person_1,
    # including the relationship connecting car_1 and person_1 is deleted,
    # requires a special query b/c TestCar has no relationship to TestPerson in the schema
    await verify_all_linked_edges_deleted(db=db, node_uuid=person_1.id, branch_name=default_branch.name)
    await verify_graph(db=db)

    node_metadata_query = await NodeMetadataDefaultBranchQuery.init(
        db=db,
        branch=default_branch,
        node_uuids=[person_1.get_id(), person_2.get_id(), car_1.get_id(), car_2.get_id()],
    )
    await node_metadata_query.execute(db=db)
    node_metadatas = node_metadata_query.get_metadatas()
    assert len(node_metadatas) == 4

    # Get metadata by node UUID for easier assertions
    metadata_by_uuid = {m.uuid: m for m in node_metadatas}

    # Validate person_1 (deleted)
    person_1_meta = metadata_by_uuid[person_1.id]
    assert person_1_meta.is_deleted is True
    assert person_1_meta.created_by == "setup-user"
    assert before_person_1_create < person_1_meta.created_at < after_person_1_create
    assert person_1_meta.updated_by == "branch-user"
    assert person_1_meta.updated_at == merge_at

    # Validate person_1's attributes (all deleted)
    for attr in person_1_meta.attributes:
        assert attr.is_deleted is True
        assert attr.created_by == "setup-user"
        assert before_person_1_create < attr.created_at < after_person_1_create
        assert attr.updated_by == "branch-user"
        assert attr.updated_at == merge_at

    # Validate person_1's relationships to car_1 and car_2 (all deleted)
    # NOTE: metadata is not set to "branch-user" because the relationships were
    # added on the default branch after branch2 was created. The car node's metadata
    # remains unchanged as "main-user".
    person_1_rel_to_car_1 = next((r for r in person_1_meta.relationships if r.peer_uuid == car_1.id), None)
    assert person_1_rel_to_car_1 is not None
    assert person_1_rel_to_car_1.is_deleted is True
    assert person_1_rel_to_car_1.created_by == "main-user"
    assert before_rel_create < person_1_rel_to_car_1.created_at < after_rel_create
    assert person_1_rel_to_car_1.updated_by == "main-user"
    assert person_1_rel_to_car_1.updated_at == person_1_rel_to_car_1.created_at

    person_1_rel_to_car_2 = next((r for r in person_1_meta.relationships if r.peer_uuid == car_2.id), None)
    assert person_1_rel_to_car_2 is not None
    assert person_1_rel_to_car_2.is_deleted is True
    assert person_1_rel_to_car_2.created_by == "main-user"
    assert before_rel_create < person_1_rel_to_car_2.created_at < after_rel_create
    assert person_1_rel_to_car_2.updated_by == "main-user"
    assert person_1_rel_to_car_2.updated_at == person_1_rel_to_car_2.created_at

    # Validate person_2 (unaffected)
    person_2_meta = metadata_by_uuid[person_2.id]
    assert person_2_meta.is_deleted is False
    assert person_2_meta.created_by == "setup-user"
    assert before_person_2_create < person_2_meta.created_at < after_person_2_create
    assert person_2_meta.updated_by == "setup-user"
    assert person_2_meta.updated_at == person_2_meta.created_at
    for attr in person_2_meta.attributes:
        assert attr.is_deleted is False
        assert before_person_2_create < attr.created_at < after_person_2_create

    # Validate car_1 (relationship deleted)
    # NOTE: Same edge case as person_1's relationships - updated_by remains "main-user"
    car_1_meta = metadata_by_uuid[car_1.id]
    assert car_1_meta.is_deleted is False
    assert car_1_meta.created_by == "setup-user"
    assert before_car_1_create < car_1_meta.created_at < after_car_1_create
    assert car_1_meta.updated_by == "main-user"
    assert before_rel_create < car_1_meta.updated_at < after_rel_create

    # Validate car_1's relationship to person_1 (deleted)
    # NOTE: Same edge case as person_1's relationships - updated_by remains "main-user"
    car_1_rel_to_person_1 = next((r for r in car_1_meta.relationships if r.peer_uuid == person_1.id), None)
    assert car_1_rel_to_person_1 is not None
    assert car_1_rel_to_person_1.is_deleted is True
    assert car_1_rel_to_person_1.created_by == "main-user"
    assert before_rel_create < car_1_rel_to_person_1.created_at < after_rel_create
    assert car_1_rel_to_person_1.updated_by == "main-user"
    assert car_1_rel_to_person_1.updated_at == car_1_rel_to_person_1.created_at

    # Validate car_2 (relationship deleted)
    # NOTE: Same edge case as car_1 - car_2's metadata is not updated
    car_2_meta = metadata_by_uuid[car_2.id]
    assert car_2_meta.is_deleted is False
    assert car_2_meta.created_by == "setup-user"
    assert before_car_2_create < car_2_meta.created_at < after_car_2_create
    assert car_2_meta.updated_by == "main-user"
    assert before_rel_create < car_2_meta.updated_at < after_rel_create

    # Validate car_2's relationship to person_1 (deleted)
    # NOTE: Same edge case as person_1's relationships - updated_by remains "main-user"
    car_2_rel_to_person_1 = next((r for r in car_2_meta.relationships if r.peer_uuid == person_1.id), None)
    assert car_2_rel_to_person_1 is not None
    assert car_2_rel_to_person_1.is_deleted is True
    assert car_2_rel_to_person_1.created_by == "main-user"
    assert before_rel_create < car_2_rel_to_person_1.created_at < after_rel_create
    assert car_2_rel_to_person_1.updated_by == "main-user"
