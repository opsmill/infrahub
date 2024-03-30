from typing import AsyncGenerator

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, RelationshipDeleteBehavior
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError


async def test_delete_succeeds(
    db: AsyncGenerator[InfrahubDatabase, None],
    default_branch: Branch,
    car_camry_main: Node,
    car_accord_main: Node,
    person_albert_main: Node,
):
    await NodeManager.delete(db=db, branch=default_branch, nodes=[person_albert_main])

    node = await NodeManager.get_one(db=db, id=person_albert_main.id)
    assert node is None


async def test_delete_prevented(
    db, default_branch, car_camry_main, car_accord_main, person_albert_main, person_jane_main
):
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
):
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
):
    car = await NodeManager.get_one(db=db, id=car_camry_main.id)
    await car.delete(db=db)

    await NodeManager.delete(db=db, branch=default_branch, nodes=[person_jane_main])

    node = await NodeManager.get_one(db=db, id=person_jane_main.id)
    assert node is None


async def test_cascade_delete_not_prevented(
    db: AsyncGenerator[InfrahubDatabase, None],
    default_branch: Branch,
    car_camry_main: Node,
    car_accord_main: Node,
    person_albert_main: Node,
    person_jane_main: Node,
):
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    person_schema = schema_branch.get(name="TestPerson", duplicate=False)
    person_schema.get_relationship("cars").delete_behavior = RelationshipDeleteBehavior.CASCADE

    await NodeManager.delete(db=db, branch=default_branch, nodes=[person_jane_main])

    node_map = await NodeManager.get_many(db=db, ids=[person_jane_main.id, car_camry_main.id])
    assert node_map == {}


async def test_delete_with_cascade_on_many_relationship(
    db, default_branch, car_camry_main, car_accord_main, car_prius_main, person_john_main, person_jane_main
):
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    person_schema = schema_branch.get(name="TestPerson", duplicate=False)
    person_schema.get_relationship("cars").delete_behavior = RelationshipDeleteBehavior.CASCADE

    await NodeManager.delete(db=db, branch=default_branch, nodes=[person_john_main])

    node_map = await NodeManager.get_many(db=db, ids=[person_john_main.id, car_accord_main.id, car_prius_main.id])
    assert node_map == {}


async def test_delete_with_cascade_on_one_relationship(
    db, default_branch, car_camry_main, car_accord_main, person_john_main
):
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    car_schema = schema_branch.get(name="TestCar", duplicate=False)
    car_schema.get_relationship("owner").delete_behavior = RelationshipDeleteBehavior.CASCADE

    await NodeManager.delete(db=db, branch=default_branch, nodes=[car_accord_main])

    node_map = await NodeManager.get_many(db=db, ids=[person_john_main.id, car_accord_main.id])
    assert node_map == {}


async def test_delete_with_cascade_multiple_input_nodes(
    db, default_branch, car_camry_main, car_accord_main, car_prius_main, person_john_main, person_jane_main
):
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    car_schema = schema_branch.get(name="TestCar", duplicate=False)
    car_schema.get_relationship("owner").delete_behavior = RelationshipDeleteBehavior.CASCADE

    await NodeManager.delete(db=db, branch=default_branch, nodes=[car_accord_main, car_prius_main])

    node_map = await NodeManager.get_many(db=db, ids=[person_john_main.id, car_accord_main.id])
    assert node_map == {}


async def test_delete_with_cascade_both_directions_succeeds(
    db, default_branch, car_camry_main, car_accord_main, car_prius_main, person_john_main, person_jane_main
):
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    car_schema = schema_branch.get(name="TestCar", duplicate=False)
    car_schema.get_relationship("owner").delete_behavior = RelationshipDeleteBehavior.CASCADE
    person_schema = schema_branch.get(name="TestPerson", duplicate=False)
    person_schema.get_relationship("cars").delete_behavior = RelationshipDeleteBehavior.CASCADE

    await NodeManager.delete(db=db, branch=default_branch, nodes=[car_accord_main])

    node_map = await NodeManager.get_many(db=db, ids=[person_john_main.id, car_accord_main.id, car_prius_main.id])
    assert node_map == {}
