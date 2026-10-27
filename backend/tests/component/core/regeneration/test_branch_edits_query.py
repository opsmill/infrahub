from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.regeneration.branch_edits import BranchEditReader
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def _create_car(db: InfrahubDatabase, branch: Branch, name: str, owner: Node) -> Node:
    car = await Node.init(db=db, schema="TestCar", branch=branch)
    await car.new(db=db, name=name, color="blue", nbr_seats=4, owner=owner.id)
    await car.save(db=db)
    return car


async def _set_color(db: InfrahubDatabase, branch: Branch, car_id: str, color: str) -> None:
    car = await NodeManager.get_one(db=db, branch=branch, id=car_id)
    car.color.value = color
    await car.save(db=db)


async def _set_owner(db: InfrahubDatabase, branch: Branch, car_id: str, owner: Node) -> None:
    car = await NodeManager.get_one(db=db, branch=branch, id=car_id)
    await car.owner.update(db=db, data=owner.id)
    await car.save(db=db)


async def test_reads_the_fields_edited_on_the_branch_after_a_time(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    person_john_main: Node,
    person_jane_main: Node,
) -> None:
    """Edits on the branch after the time are returned per field, including a relationship added and removed again."""
    reverted_car = await _create_car(db, default_branch, "reverted", person_john_main)
    recolored_car = await _create_car(db, default_branch, "recolored", person_john_main)
    early_car = await _create_car(db, default_branch, "early", person_john_main)
    branch = await create_branch(db=db, branch_name="branch-edits")

    await _set_color(db, branch, early_car.id, "red")
    since = Timestamp()
    await _set_owner(db, branch, reverted_car.id, person_jane_main)
    await _set_owner(db, branch, reverted_car.id, person_john_main)
    await _set_color(db, branch, recolored_car.id, "green")
    await _set_color(db, default_branch, early_car.id, "yellow")
    person = await NodeManager.get_one(db=db, branch=branch, id=person_jane_main.id)
    person.height.value = 170
    await person.save(db=db)
    passing_car = await _create_car(db, branch, "passing", person_john_main)
    passing_car_on_branch = await NodeManager.get_one(db=db, branch=branch, id=passing_car.id)
    await passing_car_on_branch.delete(db=db)

    edits = await BranchEditReader(db=db).read(branch=branch, since=since, kinds=["TestCar"])

    owner_identifier = car_person_schema.get(name="TestCar").get_relationship(name="owner").get_identifier()
    existing_car_edits = {
        (edit.node_id, edit.kind, edit.field_name, edit.is_relationship)
        for edit in edits
        if edit.node_id != passing_car.id
    }
    assert existing_car_edits == {
        (reverted_car.id, "TestCar", owner_identifier, True),
        (recolored_car.id, "TestCar", "color", False),
        (recolored_car.id, "TestCar", "display_label", False),
    }
    assert all(edit.edited_at > since for edit in edits)
    lifetimes = {edit.node_id: (edit.node_created_at is not None, edit.node_removed_at is not None) for edit in edits}
    assert lifetimes == {
        reverted_car.id: (False, False),
        recolored_car.id: (False, False),
        passing_car.id: (True, True),
    }

    person_edits = await BranchEditReader(db=db).read(branch=branch, since=since, kinds=["TestPerson"])

    assert {(edit.node_id, edit.field_name, edit.is_relationship) for edit in person_edits} == {
        (person_jane_main.id, owner_identifier, True),
        (person_jane_main.id, "height", False),
        (person_john_main.id, owner_identifier, True),
    }
