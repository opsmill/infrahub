import pytest

from infrahub.core.node.constraints.delete import NodeDeleteConstraint
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
