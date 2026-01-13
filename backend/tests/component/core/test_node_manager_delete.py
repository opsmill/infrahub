from typing import AsyncGenerator

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, RelationshipDeleteBehavior
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp


async def test_delete_succeeds(
    db: AsyncGenerator[InfrahubDatabase, None],
    default_branch: Branch,
    car_camry_main: Node,
    car_accord_main: Node,
    person_albert_main: Node,
) -> None:
    deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[person_albert_main])

    assert {d.id for d in deleted} == {person_albert_main.id}
    node = await NodeManager.get_one(db=db, id=person_albert_main.id)
    assert node is None


async def test_delete_prevented(
    db, default_branch, car_camry_main, car_accord_main, person_albert_main, person_jane_main
) -> None:
    with pytest.raises(ValidationError) as exc:
        await NodeManager.delete(db=db, branch=default_branch, nodes=[person_jane_main])

    assert f"Cannot delete TestPerson '{person_jane_main.id}'" in str(exc.value)
    assert f"It is linked to mandatory relationship owner on node TestCar '{car_camry_main.id}'" in str(exc.value)

    retrieved_jane = await NodeManager.get_one(db=db, id=person_jane_main.id)
    assert retrieved_jane.id == person_jane_main.id


async def test_one_sided_relationship(
    db,
    default_branch,
    car_camry_main,
    car_accord_main,
    person_albert_main,
    person_jane_main,
    car_person_schema_unregistered,
) -> None:
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    person_schema = schema_branch.get(name="TestPerson", duplicate=False)
    person_schema.relationships.append(
        RelationshipSchema(
            name="other_car",
            peer="TestCar",
            identifier="person__other_car",
            optional=True,
            cardinality="one",
            branch=BranchSupportType.AWARE,
        )
    )
    jane = await NodeManager.get_one(db=db, id=person_jane_main.id, branch=default_branch)
    await jane.other_car.update(db=db, data=car_accord_main)
    await jane.save(db=db)

    with pytest.raises(ValidationError) as exc:
        await NodeManager.delete(db=db, branch=default_branch, nodes=[jane])

    assert f"Cannot delete TestPerson '{person_jane_main.id}'" in str(exc.value)
    assert f"It is linked to mandatory relationship owner on node TestCar '{car_camry_main.id}'" in str(exc.value)

    retrieved_jane = await NodeManager.get_one(db=db, id=person_jane_main.id)
    assert retrieved_jane.id == person_jane_main.id


async def test_source_node_already_deleted(
    db, default_branch, car_camry_main, car_accord_main, person_albert_main, person_jane_main
) -> None:
    car = await NodeManager.get_one(db=db, id=car_camry_main.id)
    await car.delete(db=db)

    deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[person_jane_main])

    assert {d.id for d in deleted} == {person_jane_main.id}
    node = await NodeManager.get_one(db=db, id=person_jane_main.id)
    assert node is None


async def test_cascade_delete_not_prevented(
    db: AsyncGenerator[InfrahubDatabase, None],
    default_branch: Branch,
    car_camry_main: Node,
    car_accord_main: Node,
    person_albert_main: Node,
    person_jane_main: Node,
) -> None:
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    person_schema = schema_branch.get(name="TestPerson", duplicate=False)
    person_schema.get_relationship("cars").on_delete = RelationshipDeleteBehavior.CASCADE

    deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[person_jane_main])

    assert {d.id for d in deleted} == {person_jane_main.id, car_camry_main.id}
    node_map = await NodeManager.get_many(db=db, ids=[person_jane_main.id, car_camry_main.id])
    assert node_map == {}


async def test_delete_with_cascade_on_many_relationship(
    db, default_branch, car_camry_main, car_accord_main, car_prius_main, person_john_main, person_jane_main
) -> None:
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    person_schema = schema_branch.get(name="TestPerson", duplicate=False)
    person_schema.get_relationship("cars").on_delete = RelationshipDeleteBehavior.CASCADE

    deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[person_john_main])

    assert {d.id for d in deleted} == {person_john_main.id, car_accord_main.id, car_prius_main.id}
    node_map = await NodeManager.get_many(db=db, ids=[person_john_main.id, car_accord_main.id, car_prius_main.id])
    assert node_map == {}


async def test_delete_with_cascade_on_one_relationship(
    db, default_branch, car_camry_main, car_accord_main, person_john_main
) -> None:
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    car_schema = schema_branch.get(name="TestCar", duplicate=False)
    car_schema.get_relationship("owner").on_delete = RelationshipDeleteBehavior.CASCADE

    deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[car_accord_main])

    assert {d.id for d in deleted} == {person_john_main.id, car_accord_main.id}
    node_map = await NodeManager.get_many(db=db, ids=[person_john_main.id, car_accord_main.id])
    assert node_map == {}


async def test_delete_with_cascade_multiple_input_nodes(
    db, default_branch, car_camry_main, car_accord_main, car_prius_main, person_john_main, person_jane_main
) -> None:
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    car_schema = schema_branch.get(name="TestCar", duplicate=False)
    car_schema.get_relationship("owner").on_delete = RelationshipDeleteBehavior.CASCADE

    deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[car_accord_main, car_prius_main])

    assert {d.id for d in deleted} == {person_john_main.id, car_accord_main.id, car_prius_main.id}
    node_map = await NodeManager.get_many(db=db, ids=[person_john_main.id, car_accord_main.id, car_prius_main.id])
    assert node_map == {}


async def test_delete_with_cascade_both_directions_succeeds(
    db, default_branch, car_camry_main, car_accord_main, car_prius_main, person_john_main, person_jane_main
) -> None:
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    car_schema = schema_branch.get(name="TestCar", duplicate=False)
    car_schema.get_relationship("owner").on_delete = RelationshipDeleteBehavior.CASCADE
    person_schema = schema_branch.get(name="TestPerson", duplicate=False)
    person_schema.get_relationship("cars").on_delete = RelationshipDeleteBehavior.CASCADE

    deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[car_accord_main])

    assert {d.id for d in deleted} == {person_john_main.id, car_accord_main.id, car_prius_main.id}
    node_map = await NodeManager.get_many(db=db, ids=[person_john_main.id, car_accord_main.id, car_prius_main.id])
    assert node_map == {}


async def test_delete_with_required_on_generic_prevented(
    db, default_branch, dependent_generics_schema: SchemaBranch
) -> None:
    human = await Node.init(db=db, schema="TestHuman", branch=default_branch)
    await human.new(db=db, name="Jane", height=180)
    await human.save(db=db)
    dog = await Node.init(db=db, schema="TestDog", branch=default_branch)
    await dog.new(db=db, name="Roofus", breed="whocares", weight=50, owner=human)
    await dog.save(db=db)

    with pytest.raises(ValidationError) as exc:
        await NodeManager.delete(db=db, branch=default_branch, nodes=[human])

    assert f"Cannot delete TestHuman '{human.id}'" in str(exc.value)
    assert f"It is linked to mandatory relationship owner on node TestDog '{dog.id}'" in str(exc.value)

    retrieved_human = await NodeManager.get_one(db=db, id=human.id)
    assert retrieved_human.id == human.id


async def test_delete_with_cascade_on_generic_allowed(
    db, default_branch, dependent_generics_schema: SchemaBranch
) -> None:
    # set TestPerson.animals to be cascade delete
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    for schema_kind in ("TestPerson", "TestHuman", "TestCylon"):
        schema = schema_branch.get(name=schema_kind, duplicate=False)
        schema.get_relationship("animals").on_delete = RelationshipDeleteBehavior.CASCADE

    human = await Node.init(db=db, schema="TestHuman", branch=default_branch)
    await human.new(db=db, name="Jane", height=180)
    await human.save(db=db)
    dog = await Node.init(db=db, schema="TestDog", branch=default_branch)
    await dog.new(db=db, name="Roofus", breed="whocares", weight=50, owner=human)
    await dog.save(db=db)

    deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[human])

    assert {d.id for d in deleted} == {human.id, dog.id}
    node_map = await NodeManager.get_many(db=db, ids=[human.id, dog.id])
    assert node_map == {}


class TestDeleteUnidirectionalRelationship(TestInfrahubApp):
    async def test_delete_unidirectional_optional_relationship(self, db, client, default_branch) -> None:
        await load_schema(db, schema=CAR_SCHEMA)

        owner = await Node.init(schema=TestKind.PERSON, db=db)
        await owner.new(db=db, name="John Doe", height=175)
        await owner.save(db=db)

        previous_owner = await Node.init(schema=TestKind.PERSON, db=db)
        await previous_owner.new(db=db, name="Eric", height=175)
        await previous_owner.save(db=db)

        koenigsegg = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await koenigsegg.new(db=db, name="Koenigsegg")
        await koenigsegg.save(db=db)

        car = await Node.init(schema=TestKind.CAR, db=db)
        await car.new(
            db=db, name="Jesko", color="Red", owner=owner, manufacturer=koenigsegg, previous_owner=previous_owner
        )
        await car.save(db=db)

        await previous_owner.delete(db=db)
        res = await NodeManager.get_many(db=db, ids=[car.id])
        rels = await res[car.id].previous_owner.get_relationships(db=db)
        assert len(rels) == 0


async def test_delete_branch_aware_node_with_branch_agnostic_attribute_on_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_global: None,
) -> None:
    """Test that deleting a branch-aware node on a branch does not delete its branch-agnostic attribute on other branches.

    The scenario:
    - TestCar is branch-aware with a branch-agnostic attribute 'nbr_seats'
    - Create a car on the default branch
    - Create new branches (branch2 and branch3)
    - Delete the car while on branch2
    - Verify the car and its branch-agnostic attribute still exist on default branch and branch3
    """
    # Create a person (owner) on default branch - TestPerson is branch-agnostic in this schema
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="John", height=180)
    await person.save(db=db)

    # Create a car on default branch with branch-agnostic attribute nbr_seats
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="TestVehicle", nbr_seats=5, color="#FF0000", is_electric=True, owner=person)
    await car.save(db=db)
    car_id = car.id

    # Verify initial state on default branch
    car_on_main = await NodeManager.get_one(db=db, id=car_id, branch=default_branch)
    assert car_on_main is not None
    assert car_on_main.nbr_seats.value == 5

    # Create a new branch
    branch2 = await create_branch(db=db, branch_name="branch2")
    branch3 = await create_branch(db=db, branch_name="branch3")

    # Get the car on branch2 and delete it
    car_on_branch2 = await NodeManager.get_one(db=db, id=car_id, branch=branch2)
    assert car_on_branch2 is not None
    await car_on_branch2.delete(db=db)

    # Verify the car is deleted on branch2
    car_on_branch2_after_delete = await NodeManager.get_one(db=db, id=car_id, branch=branch2)
    assert car_on_branch2_after_delete is None

    # Verify the car still exists on default branch with its branch-agnostic attribute intact
    car_on_main_after_delete = await NodeManager.get_one(db=db, id=car_id, branch=default_branch)
    assert car_on_main_after_delete is not None, (
        "Car should still exist on default branch after being deleted on branch2"
    )
    assert car_on_main_after_delete.nbr_seats.value == 5, (
        "Branch-agnostic attribute 'nbr_seats' should not be deleted on default branch "
        "when the node is deleted on another branch"
    )

    # Verify the car still exists on branch3 with its branch-agnostic attribute intact
    car_on_branch3 = await NodeManager.get_one(db=db, id=car_id, branch=branch3)
    assert car_on_branch3 is not None
    assert car_on_branch3.nbr_seats.value == 5, (
        "Branch-agnostic attribute 'nbr_seats' should not be deleted on branch3 "
        "when the node is deleted on another branch"
    )
