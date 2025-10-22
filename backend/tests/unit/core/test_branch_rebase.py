from uuid import uuid4

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.context import InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.branch.tasks import rebase_branch
from infrahub.core.constants import InfrahubKind, MetadataOptions
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from infrahub.workers.dependencies import build_database


async def test_rebase_graph(db: InfrahubDatabase, base_dataset_02, register_core_models_schema) -> None:
    branch1 = await Branch.get_by_name(name="branch1", db=db)
    await branch1.rebase(db=db)

    # Query all cars in MAIN, AFTER the rebase
    cars = sorted(await NodeManager.query(schema="TestCar", db=db), key=lambda c: c.id)
    assert len(cars) == 2
    assert cars[0].id == "c1"
    assert cars[0].nbr_seats.value == 5
    assert cars[0].nbr_seats.is_protected is False

    # Query all cars in BRANCH1, AFTER the REBASE
    cars = sorted(await NodeManager.query(schema="TestCar", branch=branch1, db=db), key=lambda c: c.id)
    assert len(cars) == 3
    assert cars[0].id == "c1"
    assert cars[0].nbr_seats.value == 4
    assert cars[0].nbr_seats.is_protected is True
    assert cars[2].id == "c3"
    assert cars[2].name.value == "volt"


async def test_rebase_graph_delete(db: InfrahubDatabase, base_dataset_02, register_core_models_schema) -> None:
    branch1 = await Branch.get_by_name(name="branch1", db=db)

    persons = sorted(await NodeManager.query(schema="TestPerson", db=db), key=lambda p: p.id)
    assert len(persons) == 3

    p3 = await NodeManager.get_one(id="p3", branch=branch1, db=db)
    await p3.delete(db=db)

    await branch1.rebase(db=db)

    # Query all cars in BRANCH1, AFTER the REBASE
    persons = sorted(await NodeManager.query(schema="TestPerson", branch=branch1, db=db), key=lambda p: p.id)
    assert len(persons) == 2


async def test_merge_relationship_many(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, register_organization_schema
) -> None:
    blue = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await blue.new(db=db, name="Blue", description="The Blue tag")
    await blue.save(db=db)

    red = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await red.new(db=db, name="red", description="The red tag")
    await red.save(db=db)

    yellow = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await yellow.new(db=db, name="yellow", description="The yellow tag")
    await yellow.save(db=db)

    org1 = await Node.init(db=db, schema="CoreOrganization", branch=default_branch)
    await org1.new(db=db, name="org1", tags=[blue])
    await org1.save(db=db)

    branch1 = await create_branch(branch_name="branch1", db=db)

    # Update the relationships for ORG1 >> TAGS in BRANCH1
    org1_branch = await NodeManager.get_one(id=org1.id, branch=branch1, db=db)
    await org1_branch.tags.update(data=[blue, red], db=db)
    await org1_branch.save(db=db)

    # Update the relationships for ORG1 >> TAGS in MAIN
    org1_main = await NodeManager.get_one(id=org1.id, db=db)
    await org1_main.tags.update(data=[blue, yellow], db=db)
    await org1_main.save(db=db)

    await branch1.rebase(db=db)

    # All Relationship are in BRANCH1 after the REBASE
    org1_branch = await NodeManager.get_one(id=org1.id, branch=branch1, db=db)
    assert len(await org1_branch.tags.get(db=db)) == 3


async def test_branch_rebase_diff_conflict(
    db: InfrahubDatabase,
    default_branch: Branch,
    workflow_local,
    dependency_provider,
    car_person_schema,
    car_camry_main,
) -> None:
    # NOTE: Ideally, this should be somewhere else for all tests to benefit from it
    with dependency_provider.scope(build_database, lambda singleton: db):  # noqa: ARG005
        branch2 = await create_branch(db=db, branch_name="branch2")
        car_main = await NodeManager.get_one(db=db, id=car_camry_main.id)
        car_main.name.value += "-main"
        await car_main.save(db=db)
        car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_camry_main.id)
        car_branch.name.value += "-branch"
        await car_branch.save(db=db)

        with pytest.raises(ValidationError, match="contains conflicts with the default branch that must be addressed"):
            await rebase_branch(
                branch=branch2.name,
                context=InfrahubContext.init(
                    branch=default_branch,
                    account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
                ),
            )


async def test_rebase_preserves_metadata(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema,
) -> None:
    """Test that rebase preserves created/updated_at/by metadata on objects, attributes, and relationships.

    Note: Rebase updates the 'from' timestamp on branch relationships to the rebase time, which affects
    how metadata timestamps are reported. The test validates that:
    1. Node-level metadata from main is preserved
    2. Attribute values are preserved
    3. updated_by is preserved
    4. Relationships are preserved with correct peers
    5. Updates on main after branch creation are visible after rebase
    """
    # Create a person in main branch
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="Alice", height=165)
    before_person_create = Timestamp()
    await person.save(db=db, user_id="person-create-user")
    after_person_create = Timestamp()

    # Create a car in main branch with owner relationship
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="pinto", nbr_seats=5, is_electric=True, owner=person)
    before_car_create = Timestamp()
    await car.save(db=db, user_id="car-create-user")
    after_car_create = Timestamp()

    # Create a branch
    branch1 = await create_branch(branch_name="branch1", db=db)

    # Modify the car on the branch (update attribute)
    car_branch = await NodeManager.get_one(id=car.id, branch=branch1, db=db)
    car_branch.nbr_seats.value = 4
    await car_branch.save(db=db, user_id="nbr-seats-update-user")

    # Create a new object on the branch
    new_person = await Node.init(db=db, schema="TestPerson", branch=branch1)
    await new_person.new(db=db, name="Bob", height=180)
    await new_person.save(db=db, user_id="new-person-create-user")

    # Update the person on main AFTER the branch was created (this should be visible after rebase)
    person_main = await NodeManager.get_one(id=person.id, db=db)
    person_main.height.value = 170
    before_person_update_main = Timestamp()
    await person_main.save(db=db, user_id="height-update-user")
    after_person_update_main = Timestamp()

    # Create a new car on main AFTER the branch was created
    car2 = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car2.new(db=db, name="model3", nbr_seats=5, is_electric=True, owner=person)
    before_car2_create = Timestamp()
    await car2.save(db=db, user_id="car2-create-user")
    after_car2_create = Timestamp()

    # Rebase the branch
    before_rebase = Timestamp()
    await branch1.rebase(db=db)
    after_rebase = Timestamp()

    # Verify metadata on objects created on main (queried from branch after rebase)
    person_after_rebase = await NodeManager.get_one(
        id=person.id, branch=branch1, db=db, include_metadata=MetadataOptions.USER_TIMESTAMPS
    )
    assert before_person_create < person_after_rebase._get_created_at() < after_person_create
    assert person_after_rebase._get_created_by() == "person-create-user"

    # Verify that updates on main after branch creation are visible after rebase
    assert person_after_rebase.height.value == 170
    assert before_person_update_main < person_after_rebase.height._get_updated_at() < after_person_update_main
    assert person_after_rebase.height._get_updated_by() == "height-update-user"

    # Verify metadata on objects created on main (car) - node-level metadata from main branch
    car_after_rebase = await NodeManager.get_one(
        id=car.id, branch=branch1, db=db, include_metadata=MetadataOptions.USER_TIMESTAMPS
    )
    # Node was created on main, so created_at/by should reflect that
    assert before_car_create < car_after_rebase._get_created_at() < after_car_create
    assert car_after_rebase._get_created_by() == "car-create-user"

    # Verify attribute value and updated_by are preserved (timestamp is updated by rebase)
    assert car_after_rebase.nbr_seats.value == 4
    assert car_after_rebase.nbr_seats._get_updated_by() == "nbr-seats-update-user"
    assert before_rebase < car_after_rebase.nbr_seats._get_updated_at() < after_rebase

    # Verify attribute that was NOT updated keeps updated_by
    assert car_after_rebase.name._get_updated_by() == "car-create-user"
    assert before_car_create < car_after_rebase.name._get_updated_at() < after_car_create
    assert car_after_rebase.name.value == "pinto"

    # Verify metadata on objects created on branch
    new_person_after_rebase = await NodeManager.get_one(
        id=new_person.id, branch=branch1, db=db, include_metadata=MetadataOptions.USER_TIMESTAMPS
    )
    assert new_person_after_rebase._get_created_by() == "new-person-create-user"
    assert before_rebase < new_person_after_rebase._get_created_at() < after_rebase
    assert new_person_after_rebase._get_updated_by() == "new-person-create-user"
    assert new_person_after_rebase._get_updated_at() == new_person_after_rebase._get_created_at()
    assert new_person_after_rebase.name.value == "Bob"

    # Verify new object created on main after branch creation is visible after rebase
    car2_after_rebase = await NodeManager.get_one(
        id=car2.id, branch=branch1, db=db, include_metadata=MetadataOptions.USER_TIMESTAMPS
    )
    assert before_car2_create < car2_after_rebase._get_created_at() < after_car2_create
    assert car2_after_rebase._get_created_by() == "car2-create-user"
    assert car2_after_rebase._get_updated_at() == car2_after_rebase._get_created_at()
    assert car2_after_rebase._get_updated_by() == "car2-create-user"
    assert car2_after_rebase.name.value == "model3"

    # Verify relationship metadata (owner relationship on car created before branch)
    car_schema = car_after_rebase.get_schema()
    owner_rels = await NodeManager.query_peers(
        db=db,
        branch=branch1,
        ids=[car.id],
        source_kind="TestCar",
        schema=car_schema.get_relationship(name="owner"),
        filters={},
        include_metadata=MetadataOptions.USER_TIMESTAMPS,
        fetch_peers=True,
    )
    assert len(owner_rels) == 1
    owner_rel = owner_rels[0]
    # Relationship was created on main before branch, so created_by should reflect that
    assert owner_rel._get_created_by() == "car-create-user"
    assert before_car_create < owner_rel._get_created_at() < after_car_create
    assert owner_rel._get_updated_by() == "car-create-user"
    assert owner_rel._get_updated_at() == owner_rel._get_created_at()
    assert owner_rel.get_peer_id() == person.id
    owner_peer = await owner_rel.get_peer(db=db)
    assert before_person_create < owner_peer._get_created_at() < after_person_create
    assert owner_peer._get_created_by() == "person-create-user"
    assert before_person_update_main < owner_peer.height._get_updated_at() < after_person_update_main
    assert owner_peer.height._get_updated_by() == "height-update-user"

    # Verify relationship metadata on car2 (created on main AFTER branch creation)
    # This validates that relationships created on main after branch creation are visible after rebase
    car2_owner_rels = await NodeManager.query_peers(
        db=db,
        branch=branch1,
        ids=[car2.id],
        source_kind="TestCar",
        schema=car_schema.get_relationship(name="owner"),
        filters={},
        include_metadata=MetadataOptions.USER_TIMESTAMPS,
        fetch_peers=True,
    )
    assert len(car2_owner_rels) == 1
    car2_owner_rel = car2_owner_rels[0]
    # Relationship was created on main after branch creation
    assert before_car2_create < car2_owner_rel._get_created_at() < after_car2_create
    assert car2_owner_rel._get_created_by() == "car2-create-user"
    assert car2_owner_rel._get_updated_at() == car2_owner_rel._get_created_at()
    assert car2_owner_rel._get_created_by() == "car2-create-user"
    assert car2_owner_rel.get_peer_id() == person.id
    owner_peer = await car2_owner_rel.get_peer(db=db)
    assert owner_peer.name.value == "Alice"
    assert before_person_create < owner_peer._get_created_at() < after_person_create
    assert owner_peer._get_created_by() == "person-create-user"
    assert before_car2_create < owner_peer._get_updated_at() < after_car2_create
    assert owner_peer._get_updated_by() == "car2-create-user"
