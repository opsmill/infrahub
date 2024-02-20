import pytest

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.node.constraints.uniqueness import NodeUniquenessConstraint
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError


async def test_node_validate_constraint_node_uniqueness_failure(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main
):
    constraint = NodeUniquenessConstraint(db=db, branch=default_branch)
    new_john = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await new_john.new(db=db, name="John", height=160)

    with pytest.raises(ValidationError) as exc:
        await constraint.check(new_john)

    assert "An object already exist with this value" in exc.value.message


async def test_node_validate_constraint_node_uniqueness_success(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main
):
    constraint = NodeUniquenessConstraint(db=db, branch=default_branch)
    alfred = await Node.init(db=db, schema="TestPerson", branch=default_branch)

    await alfred.new(db=db, name="Alfred", height=160)

    await constraint.check(alfred)
