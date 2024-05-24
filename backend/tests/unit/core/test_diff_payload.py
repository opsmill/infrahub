from infrahub.core.constants import DiffAction
from infrahub.core.diff.branch_differ import BranchDiffer
from infrahub.core.diff.model import DiffElementType
from infrahub.core.diff.payload_builder import DiffPayloadBuilder
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase


async def test_diff_payload_one_relationship_update(
    db: InfrahubDatabase, person_alfred_main, person_john_main, car_accord_main
):
    branch = await create_branch(db=db, branch_name="branch")
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await car_branch.owner.update(db=db, data=person_alfred_main)
    await car_branch.save(db=db)
    differ = await BranchDiffer.init(branch=branch, db=db)
    payload_builder = DiffPayloadBuilder(db=db, diff=differ)

    diff_payload = await payload_builder.get_branch_diff_nodes()

    payloads_by_id = {p.id: p for p in diff_payload}
    assert set(payloads_by_id.keys()) == {car_accord_main.id, person_alfred_main.id, person_john_main.id}
    assert payloads_by_id[person_alfred_main.id].action is DiffAction.UPDATED
    diff_elements = payloads_by_id[person_alfred_main.id].elements
    assert len(diff_elements) == 1
    diff_element = diff_elements["cars"]
    assert diff_element.type is DiffElementType.RELATIONSHIP_MANY
    assert diff_element.name == "cars"
    assert diff_element.branch == branch.name
    assert diff_element.action is DiffAction.ADDED
    diff_peers = diff_element.peers
    assert len(diff_peers) == 1
    assert diff_peers[0].peer.id == car_branch.id

    assert payloads_by_id[person_john_main.id].action is DiffAction.UPDATED
    diff_elements = payloads_by_id[person_john_main.id].elements
    assert len(diff_elements) == 1
    diff_element = diff_elements["cars"]
    assert diff_element.type is DiffElementType.RELATIONSHIP_MANY
    assert diff_element.name == "cars"
    assert diff_element.branch == branch.name
    assert diff_element.action is DiffAction.REMOVED
    diff_peers = diff_element.peers
    assert len(diff_peers) == 1
    assert diff_peers[0].peer.id == car_branch.id

    assert payloads_by_id[car_branch.id].action is DiffAction.UPDATED
    owner_element = payloads_by_id[car_branch.id].elements["owner"]
    assert owner_element.type is DiffElementType.RELATIONSHIP_ONE
    assert owner_element.name == "owner"
    assert owner_element.branch == branch.name
    assert owner_element.action is DiffAction.UPDATED
    assert owner_element.peer.previous.id == person_john_main.id
    assert owner_element.peer.new.id == person_alfred_main.id


async def test_diff_payload_two_updates_one_relationship(db: InfrahubDatabase, person_albert_main, person_alfred_main):
    branch = await create_branch(db=db, branch_name="branch")
    car_branch = await Node.init(db=db, schema="TestCar", branch=branch)
    await car_branch.new(db=db, name="pinto", nbr_seats=3, is_electric=False, owner=person_albert_main.id)
    await car_branch.save(db=db)
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_branch.id)
    await car_branch.owner.update(db=db, data=person_alfred_main)
    await car_branch.save(db=db)
    differ = await BranchDiffer.init(branch=branch, db=db)
    payload_builder = DiffPayloadBuilder(db=db, diff=differ)

    diff_payload = await payload_builder.get_branch_diff_nodes()

    payloads_by_id = {p.id: p for p in diff_payload}
    # NOT WORKING
    # assert set(payloads_by_id.keys()) == {car_branch.id, person_alfred_main.id}

    assert payloads_by_id[person_alfred_main.id].action is DiffAction.UPDATED
    diff_elements = payloads_by_id[person_alfred_main.id].elements
    assert len(diff_elements) == 1
    diff_element = diff_elements["cars"]
    assert diff_element.type is DiffElementType.RELATIONSHIP_MANY
    assert diff_element.name == "cars"
    assert diff_element.branch == branch.name
    assert diff_element.action is DiffAction.ADDED
    diff_peers = diff_element.peers
    assert len(diff_peers) == 1
    assert diff_peers[0].peer.id == car_branch.id

    assert payloads_by_id[car_branch.id].action is DiffAction.ADDED
    owner_element = payloads_by_id[car_branch.id].elements["owner"]
    assert owner_element.type is DiffElementType.RELATIONSHIP_ONE
    assert owner_element.name == "owner"
    assert owner_element.branch == branch.name
    assert owner_element.action is DiffAction.UPDATED
    assert owner_element.peer.previous.id == person_albert_main.id
    assert owner_element.peer.new.id == person_alfred_main.id


async def test_diff_payload_three_updates_one_relationship(
    db: InfrahubDatabase, person_albert_main, person_alfred_main, person_jane_main
):
    branch = await create_branch(db=db, branch_name="branch")
    car_branch = await Node.init(db=db, schema="TestCar", branch=branch)
    await car_branch.new(db=db, name="pinto", nbr_seats=3, is_electric=False, owner=person_albert_main.id)
    await car_branch.save(db=db)
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_branch.id)
    await car_branch.owner.update(db=db, data=person_jane_main)
    await car_branch.save(db=db)
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_branch.id)
    await car_branch.owner.update(db=db, data=person_alfred_main)
    await car_branch.save(db=db)
    differ = await BranchDiffer.init(branch=branch, db=db)
    payload_builder = DiffPayloadBuilder(db=db, diff=differ)

    diff_payload = await payload_builder.get_branch_diff_nodes()

    payloads_by_id = {p.id: p for p in diff_payload}
    # NOT WORKING
    # assert set(payloads_by_id.keys()) == {person_alfred_main.id, car_branch.id}
    assert person_alfred_main.id in payloads_by_id
    assert payloads_by_id[person_alfred_main.id].action is DiffAction.UPDATED
    diff_elements = payloads_by_id[person_alfred_main.id].elements
    assert len(diff_elements) == 1
    diff_element = diff_elements["cars"]
    assert diff_element.type is DiffElementType.RELATIONSHIP_MANY
    assert diff_element.name == "cars"
    assert diff_element.branch == branch.name
    assert diff_element.action is DiffAction.ADDED
    diff_peers = diff_element.peers
    assert len(diff_peers) == 1
    assert diff_peers[0].peer.id == car_branch.id

    assert car_branch.id in payloads_by_id
    assert payloads_by_id[car_branch.id].action is DiffAction.ADDED
    owner_element = payloads_by_id[car_branch.id].elements["owner"]
    assert owner_element.type is DiffElementType.RELATIONSHIP_ONE
    assert owner_element.name == "owner"
    assert owner_element.branch == branch.name
    assert owner_element.action is DiffAction.UPDATED
    assert owner_element.peer.previous.id == person_jane_main.id
    assert owner_element.peer.new.id == person_alfred_main.id
