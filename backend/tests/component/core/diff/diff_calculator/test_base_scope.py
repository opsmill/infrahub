from infrahub.core.branch import Branch
from infrahub.core.diff.calculator import DiffCalculator
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


async def test_base_changes_still_scoped_to_branch_changes(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, person_john_main: Node
) -> None:
    """Base changes on a field the branch also changed are kept; base changes on other nodes are not."""
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp()
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    car_branch.nbr_seats.value = 7
    await car_branch.save(db=db)
    car_main = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    car_main.nbr_seats.value = 10
    await car_main.save(db=db)
    person_main = await NodeManager.get_one(db=db, branch=default_branch, id=person_john_main.id)
    person_main.height.value = 200
    await person_main.save(db=db)

    calculated_diffs = await DiffCalculator(db=db).calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    assert {n.uuid for n in calculated_diffs.base_branch_diff.nodes} == {car_accord_main.id}
    assert {n.uuid for n in calculated_diffs.diff_branch_diff.nodes} == {car_accord_main.id}
