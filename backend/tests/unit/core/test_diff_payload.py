from infrahub.core.constants import DiffAction
from infrahub.core.diff.branch_differ import BranchDiffer
from infrahub.core.diff.model import DiffElementType
from infrahub.core.diff.payload_builder import DiffPayloadBuilder
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase


async def test_diff_payload_multiple_relationship_change(
    db: InfrahubDatabase, person_albert_main, person_alfred_main, person_jane_main
):
    branch = await create_branch(db=db, branch_name="branch")
    car_branch = await Node.init(db=db, schema="TestCar", branch=branch)
    await car_branch.new(db=db, name="pinto", nbr_seats=3, is_electric=False, owner=person_albert_main.id)
    await car_branch.save(db=db)
    await car_branch.owner.update(db=db, data=person_alfred_main)
    await car_branch.save(db=db)
    differ = await BranchDiffer.init(branch=branch, db=db)
    payload_builder = DiffPayloadBuilder(db=db, diff=differ)

    diff_payload = await payload_builder.get_branch_diff_nodes()

    assert len(diff_payload) == 3
    payloads_by_id = {p.id: p for p in diff_payload}
    assert set(payloads_by_id.keys()) == {car_branch.id, person_alfred_main.id, person_albert_main.id}
    assert payloads_by_id[person_albert_main.id].action is DiffAction.UPDATED
    diff_elements = payloads_by_id[person_albert_main.id].elements
    assert len(diff_elements) == 1
    diff_element = diff_elements["cars"]
    assert diff_element.type is DiffElementType.RELATIONSHIP_MANY
    assert diff_element.name == "cars"
    assert diff_element.branch == branch.name
    assert diff_element.action is DiffAction.ADDED
    diff_peers = diff_element.peers
    assert len(diff_peers) == 1
    assert diff_peers[0].peer.id == car_branch.id

    assert payloads_by_id[person_alfred_main.id].action is DiffAction.UPDATED
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
    assert owner_element.action is DiffAction.ADDED
    assert owner_element.peer.previous is None
    assert owner_element.peer.new.id == person_alfred_main.id
