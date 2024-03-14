import pytest

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.relationship.constraints.count import RelationshipCountConstraint
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError


async def test_node_validate_constraint_relationship_count_failure(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main
):
    constraint = RelationshipCountConstraint(db=db, branch=default_branch)
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="Alfred", height=160, cars=[car_accord_main.id])

    with pytest.raises(ValidationError) as exc:
        await constraint.check(person.cars)

    assert "has 2 peers for testcar__testperson, maximum of 1 allowed" in exc.value.message


async def test_node_validate_constraint_relationship_count_success(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main
):
    constraint = RelationshipCountConstraint(db=db, branch=default_branch)

    await constraint.check(person_john_main.cars)
