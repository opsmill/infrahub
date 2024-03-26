import pytest

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType
from infrahub.core.manager import NodeManager
from infrahub.core.node.constraints.delete import NodeDeleteConstraint
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.exceptions import ValidationError


async def test_delete_allowed(db, default_branch, car_camry_main, car_accord_main, person_albert_main):
    constraint = NodeDeleteConstraint(db=db, branch=default_branch)

    await constraint.check(node=person_albert_main)


async def test_delete_prevented(
    db, default_branch, car_camry_main, car_accord_main, person_albert_main, person_jane_main
):
    constraint = NodeDeleteConstraint(db=db, branch=default_branch)

    with pytest.raises(ValidationError) as exc:
        await constraint.check(node=person_jane_main)

    assert "Cannot delete. Node is linked to mandatory relationship" in str(exc.value)
    assert f"{car_camry_main.id} at TestCar.owner" in str(exc.value)


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
    constraint = NodeDeleteConstraint(db=db, branch=default_branch)

    with pytest.raises(ValidationError) as exc:
        await constraint.check(node=jane)

    assert "Cannot delete. Node is linked to mandatory relationship" in str(exc.value)
    assert f"{car_camry_main.id} at TestCar.owner" in str(exc.value)
