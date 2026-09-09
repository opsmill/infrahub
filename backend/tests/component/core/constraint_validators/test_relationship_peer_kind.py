import pytest

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.query.node import NodeListGetInfoQuery
from infrahub.core.relationship.constraints.peer_kind import RelationshipPeerKindConstraint
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from tests.helpers.db_query_counter import CountingInfrahubDatabase


async def test_peer_given_as_a_node_is_not_read_back(
    db: InfrahubDatabase, default_branch: Branch, person_john_main: Node, car_person_schema: None
) -> None:
    """A peer the caller hands over states its own kind."""
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="accord", nbr_seats=5, is_electric=False, owner=person_john_main)
    counting_db = CountingInfrahubDatabase.from_db(db=db)
    constraint = RelationshipPeerKindConstraint(db=counting_db, branch=default_branch)

    await constraint.check(relm=car.owner, node_schema=car.get_schema(), node=car)

    assert counting_db.count_for(NodeListGetInfoQuery.name) == 0


async def test_peer_given_as_a_node_of_the_wrong_kind_is_rejected(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_person_schema: None
) -> None:
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="civic", nbr_seats=5, is_electric=False, owner=car_accord_main)
    constraint = RelationshipPeerKindConstraint(db=db, branch=default_branch)

    with pytest.raises(ValidationError, match="cannot be added to relationship, must be of type"):
        await constraint.check(relm=car.owner, node_schema=car.get_schema(), node=car)


async def test_peer_given_by_id_of_the_wrong_kind_is_rejected(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_person_schema: None
) -> None:
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="civic", nbr_seats=5, is_electric=False, owner=car_accord_main.id)
    constraint = RelationshipPeerKindConstraint(db=db, branch=default_branch)

    with pytest.raises(ValidationError, match="cannot be added to relationship, must be of type"):
        await constraint.check(relm=car.owner, node_schema=car.get_schema(), node=car)
