from dataclasses import dataclass

import pytest

from infrahub.core.branch import Branch
from infrahub.core.diff.calculator import DiffCalculator
from infrahub.core.diff.model.field_specifiers_map import NodeFieldSpecifierMap
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


@dataclass
class UnchangedBranchCase:
    name: str
    previous_node_specifiers: NodeFieldSpecifierMap | None


UNCHANGED_BRANCH_CASES = [
    UnchangedBranchCase(name="first_calculation", previous_node_specifiers=None),
    UnchangedBranchCase(name="after_an_empty_diff", previous_node_specifiers=NodeFieldSpecifierMap()),
]


@pytest.mark.parametrize("case", UNCHANGED_BRANCH_CASES, ids=lambda case: case.name)
async def test_base_changes_ignored_when_branch_has_no_changes(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    person_john_main: Node,
    case: UnchangedBranchCase,
) -> None:
    """The base-branch diff holds only base changes to fields the branch changed too, so none for an unchanged branch."""
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.get_branched_from())
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
        previous_node_specifiers=case.previous_node_specifiers,
    )

    assert calculated_diffs.diff_branch_diff.nodes == []
    assert calculated_diffs.base_branch_diff.nodes == []
