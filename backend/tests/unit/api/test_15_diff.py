import pytest

from infrahub.api.diff import get_display_labels, get_display_labels_per_kind
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.message_bus.events import (
    GitMessageAction,
    InfrahubRPCResponse,
    MessageType,
    RPCStatusCode,
)
from infrahub.message_bus.rpc import InfrahubRpcClientTesting


@pytest.fixture
def patch_rpc_client():
    import infrahub.message_bus.rpc

    infrahub.message_bus.rpc.InfrahubRpcClient = InfrahubRpcClientTesting


async def test_diff_files_endpoint(
    session, patch_rpc_client, default_branch: Branch, client, client_headers, repos_in_main
):
    branch2 = await create_branch(branch_name="branch2", session=session)

    repos_list = await NodeManager.query(session=session, schema="Repository", branch=branch2)
    repos = {repo.name.value: repo for repo in repos_list}

    repo01 = repos["repo01"]
    repo01.commit.value = "dddddddddd"
    await repo01.save(session=session)

    repo02 = repos["repo02"]
    repo02.commit.value = "eeeeeeeeee"
    await repo02.save(session=session)

    with client:
        mock_response = InfrahubRPCResponse(
            status=RPCStatusCode.OK.value, response={"files_changed": ["readme.md", "mydir/myfile.py"]}
        )
        await client.app.state.rpc_client.add_response(
            response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.DIFF
        )
        mock_response = InfrahubRPCResponse(
            status=RPCStatusCode.OK.value, response={"files_changed": ["anotherfile.rb"]}
        )
        await client.app.state.rpc_client.add_response(
            response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.DIFF
        )

        response = client.get(
            "/diff/files?branch=branch2",
            headers=client_headers,
        )

    assert response.status_code == 200
    assert response.json() is not None


async def test_get_display_labels_per_kind(session, default_branch, car_person_data):
    persons_list = await NodeManager.query(session=session, schema="Person", branch=default_branch)
    person_ids = [item.id for item in persons_list]
    display_labels = await get_display_labels_per_kind(
        kind="Person", ids=person_ids, branch_name=default_branch.name, session=session
    )
    assert len(display_labels) == len(person_ids)


async def test_get_display_labels_per_kind_with_branch(session, default_branch, car_person_data):
    branch2 = await create_branch(branch_name="branch2", session=session)

    # Add a new Person
    p3 = await Node.init(session=session, schema="Person", branch=branch2)
    await p3.new(session=session, name="Bill", height=160)
    await p3.save(session=session)

    persons_list = await NodeManager.query(session=session, schema="Person", branch=branch2)
    person_ids = [item.id for item in persons_list]

    display_labels = await get_display_labels_per_kind(
        kind="Person", ids=person_ids, branch_name=branch2.name, session=session
    )
    assert len(display_labels) == len(person_ids)


async def test_get_display_labels(session, default_branch, car_person_data):
    persons_list = await NodeManager.query(session=session, schema="Person", branch=default_branch)
    person_ids = [item.id for item in persons_list]
    cars_list = await NodeManager.query(session=session, schema="Car", branch=default_branch)
    car_ids = [item.id for item in cars_list]

    display_labels = await get_display_labels(nodes={"main": {"Person": person_ids, "Car": car_ids}}, session=session)
    assert len(display_labels) == len(car_ids) + len(person_ids)


async def test_get_display_labels_with_branch(session, default_branch, car_person_data):
    branch2 = await create_branch(branch_name="branch2", session=session)

    persons_list = await NodeManager.query(session=session, schema="Person", branch=branch2)
    persons = {item.name.value: item for item in persons_list}

    repos_list = await NodeManager.query(session=session, schema="Repository", branch=branch2)
    repos = {item.name.value: item for item in repos_list}

    cars_list = await NodeManager.query(session=session, schema="Car", branch=branch2)
    cars = {item.name.value: item for item in cars_list}

    # Add a new Person
    p3 = await Node.init(session=session, schema="Person", branch=branch2)
    await p3.new(session=session, name="Bill", height=160)
    await p3.save(session=session)
    persons["Bill"] = p3

    await cars["volt"].owner.update(data=p3, session=session)
    await cars["volt"].save(session=session)

    repo01 = repos["repo01"]
    repo01.commit.value = "dddddddddd"
    await repo01.save(session=session)

    # Update P1 height in main
    p1 = await NodeManager.get_one(id=persons["John"].id, session=session)
    p1.height.value = 120
    await p1.save(session=session)

    persons_list = await NodeManager.query(session=session, schema="Person", branch=branch2)
    person_ids = [item.id for item in persons_list]
    cars_list = await NodeManager.query(session=session, schema="Car", branch=branch2)
    car_ids = [item.id for item in cars_list]

    display_labels = await get_display_labels(
        nodes={branch2.name: {"Person": person_ids, "Car": car_ids}}, session=session
    )
    assert len(display_labels) == len(car_ids) + len(person_ids)


async def test_diff_data_endpoint_branch_only(session, client, client_headers, default_branch, car_person_data):
    branch2 = await create_branch(branch_name="branch2", session=session)

    persons_list = await NodeManager.query(session=session, schema="Person", branch=branch2)
    persons = {item.name.value: item for item in persons_list}

    repos_list = await NodeManager.query(session=session, schema="Repository", branch=branch2)
    repos = {item.name.value: item for item in repos_list}

    cars_list = await NodeManager.query(session=session, schema="Car", branch=branch2)
    cars = {item.name.value: item for item in cars_list}

    # Add a new Person
    p3 = await Node.init(session=session, schema="Person", branch=branch2)
    await p3.new(session=session, name="Bill", height=160)
    await p3.save(session=session)
    persons["Bill"] = p3

    await cars["volt"].owner.update(data=p3, session=session)
    await cars["volt"].save(session=session)

    repo01 = repos["repo01"]
    repo01.commit.value = "dddddddddd"
    await repo01.save(session=session)

    # Update P1 height in main
    p1 = await NodeManager.get_one(id=persons["John"].id, session=session)
    p1.height.value = 120
    await p1.save(session=session)

    with client:
        response = client.get(
            "/diff/data?branch=branch2&branch_only=true",
            headers=client_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert list(data.keys()) == ["branch2"]
    assert len(data["branch2"]) == 3


async def test_diff_data_endpoint_with_main(session, client, client_headers, default_branch, car_person_data):
    branch2 = await create_branch(branch_name="branch2", session=session)

    persons_list = await NodeManager.query(session=session, schema="Person", branch=branch2)
    persons = {item.name.value: item for item in persons_list}

    repos_list = await NodeManager.query(session=session, schema="Repository", branch=branch2)
    repos = {item.name.value: item for item in repos_list}

    # Add a new Person
    p3 = await Node.init(session=session, schema="Person", branch=branch2)
    await p3.new(session=session, name="Bill", height=160)
    await p3.save(session=session)
    persons["Bill"] = p3

    repo01 = repos["repo01"]
    repo01.commit.value = "dddddddddd"
    await repo01.save(session=session)

    # Update P1 height and C1 in main
    p1 = await NodeManager.get_one(id=persons["John"].id, session=session)
    p1.height.value = 120
    await p1.save(session=session)

    cars_list = await NodeManager.query(session=session, schema="Car", branch=default_branch)
    cars = {item.name.value: item for item in cars_list}

    await cars["volt"].owner.update(data=persons["Jane"].id, session=session)
    await cars["volt"].save(session=session)

    with client:
        response = client.get(
            "/diff/data?branch=branch2&branch_only=false",
            headers=client_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert sorted(data.keys()) == ["branch2", "main"]
    assert len(data["branch2"]) == 2
    assert len(data["main"]) == 3
