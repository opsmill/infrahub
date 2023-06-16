import pytest

from infrahub.api.diff import get_display_labels, get_display_labels_per_kind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.message_bus.rpc import InfrahubRpcClientTesting


@pytest.fixture
def patch_rpc_client():
    import infrahub.message_bus.rpc

    infrahub.message_bus.rpc.InfrahubRpcClient = InfrahubRpcClientTesting


async def test_get_display_labels_per_kind(session, default_branch, car_person_data):
    persons_list = await NodeManager.query(session=session, schema="TestPerson", branch=default_branch)
    person_ids = [item.id for item in persons_list]
    display_labels = await get_display_labels_per_kind(
        kind="TestPerson", ids=person_ids, branch_name=default_branch.name, session=session
    )
    assert len(display_labels) == len(person_ids)


async def test_get_display_labels_per_kind_with_branch(session, default_branch, car_person_data):
    branch2 = await create_branch(branch_name="branch2", session=session)

    # Add a new Person
    p3 = await Node.init(session=session, schema="TestPerson", branch=branch2)
    await p3.new(session=session, name="Bill", height=160)
    await p3.save(session=session)

    persons_list = await NodeManager.query(session=session, schema="TestPerson", branch=branch2)
    person_ids = [item.id for item in persons_list]

    display_labels = await get_display_labels_per_kind(
        kind="TestPerson", ids=person_ids, branch_name=branch2.name, session=session
    )
    assert len(display_labels) == len(person_ids)


async def test_get_display_labels(session, default_branch, car_person_data):
    persons_list = await NodeManager.query(session=session, schema="TestPerson", branch=default_branch)
    person_ids = [item.id for item in persons_list]
    cars_list = await NodeManager.query(session=session, schema="TestCar", branch=default_branch)
    car_ids = [item.id for item in cars_list]

    display_labels = await get_display_labels(
        nodes={"main": {"TestPerson": person_ids, "TestCar": car_ids}}, session=session
    )
    assert len(display_labels) == len(car_ids) + len(person_ids)


async def test_get_display_labels_with_branch(session, default_branch, car_person_data):
    branch2 = await create_branch(branch_name="branch2", session=session)

    persons_list = await NodeManager.query(session=session, schema="TestPerson", branch=branch2)
    persons = {item.name.value: item for item in persons_list}

    repos_list = await NodeManager.query(session=session, schema="CoreRepository", branch=branch2)
    repos = {item.name.value: item for item in repos_list}

    cars_list = await NodeManager.query(session=session, schema="TestCar", branch=branch2)
    cars = {item.name.value: item for item in cars_list}

    # Add a new Person
    p3 = await Node.init(session=session, schema="TestPerson", branch=branch2)
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

    persons_list = await NodeManager.query(session=session, schema="TestPerson", branch=branch2)
    person_ids = [item.id for item in persons_list]
    cars_list = await NodeManager.query(session=session, schema="TestCar", branch=branch2)
    car_ids = [item.id for item in cars_list]

    display_labels = await get_display_labels(
        nodes={branch2.name: {"TestPerson": person_ids, "TestCar": car_ids}}, session=session
    )
    assert len(display_labels) == len(car_ids) + len(person_ids)


async def test_diff_data_endpoint_branch_only_default(session, client, client_headers, car_person_data_generic_diff):
    c1 = car_person_data_generic_diff["c1"]
    c4 = car_person_data_generic_diff["c4"]
    p1 = car_person_data_generic_diff["p1"]
    p2 = car_person_data_generic_diff["p2"]
    p3 = car_person_data_generic_diff["p3"]
    r1 = car_person_data_generic_diff["r1"]

    with client:
        response = client.get(
            "/diff/data?branch=branch2&branch_only=true",
            headers=client_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data is not None

    assert list(data.keys()) == ["branch2"]
    branch2 = {node["id"]: node for node in data["branch2"]}

    assert branch2[p1]["display_label"] == "John"
    assert branch2[p1]["kind"] == "TestPerson"
    assert branch2[p1]["action"] == "updated"
    assert branch2[p1]["summary"] == {"added": 0, "removed": 1, "updated": 0}
    assert branch2[p1]["elements"]["cars"]["peers"][0]["peer"]["id"] == c1
    assert branch2[p1]["elements"]["cars"]["peers"][0]["peer"]["kind"] == "TestElectricCar"

    assert branch2[p2]["display_label"] == "Jane"
    assert branch2[p2]["kind"] == "TestPerson"
    assert branch2[p2]["action"] == "updated"
    assert branch2[p2]["summary"] == {"added": 0, "removed": 1, "updated": 0}
    assert branch2[p2]["elements"]["cars"]["peers"][0]["peer"]["id"] == c4
    assert branch2[p2]["elements"]["cars"]["peers"][0]["peer"]["kind"] == "TestGazCar"

    assert branch2[p3]["display_label"] == "Bill"
    assert branch2[p3]["action"] == "added"
    assert branch2[p3]["summary"] == {"added": 3, "removed": 0, "updated": 0}
    assert branch2[p3]["elements"]["cars"]["peers"][0]["peer"]["id"] == c1
    assert len(branch2[p3]["elements"]["name"]["properties"]) == 2

    assert branch2[c1]["kind"] == "TestElectricCar"
    assert branch2[c1]["action"] == "updated"
    assert branch2[c1]["summary"] == {"added": 0, "removed": 0, "updated": 1}
    assert branch2[c1]["elements"]["owner"]["peer"]["new"]["id"] == p3
    assert branch2[c1]["elements"]["owner"]["peer"]["previous"]["id"] == p1
    # assert branch2[c1]["elements"]["owner"]["summary"] = {'added': 0, 'removed': 0, 'updated': 0}

    assert branch2[c4]["kind"] == "TestGazCar"
    assert branch2[c4]["action"] == "removed"
    assert branch2[c4]["summary"] == {"added": 0, "removed": 5, "updated": 0}
    assert branch2[c4]["elements"]["owner"]["peer"]["previous"]["id"] == p2

    assert branch2[r1]["kind"] == "CoreRepository"
    assert branch2[r1]["action"] == "updated"
    assert branch2[r1]["summary"] == {"added": 0, "removed": 0, "updated": 1}
    assert branch2[r1]["elements"]["commit"]["value"]["value"]["new"] == "dddddddddd"
    # assert branch2[r1]["elements"]["commit"]["value"]["value"]['previous'] == "aaaaaaaaa" FIXME
    assert (
        branch2[r1]["elements"]["commit"]["value"]["changed_at"]
        == car_person_data_generic_diff["time21"].to_iso8601_string()
    )


@pytest.mark.xfail(reason="Need to investigate, occasionally fails")
async def test_diff_data_endpoint_branch_time_from(session, client, client_headers, car_person_data_generic_diff):
    time20 = car_person_data_generic_diff["time20"]

    c4 = car_person_data_generic_diff["c4"]
    p2 = car_person_data_generic_diff["p2"]
    r1 = car_person_data_generic_diff["r1"]

    with client:
        response = client.get(
            f"/diff/data?branch=branch2&branch_only=true&time_from={time20.to_iso8601_string()}",
            headers=client_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert list(data.keys()) == ["branch2"]
    assert len(data["branch2"]) == 3

    branch2 = {node["id"]: node for node in data["branch2"]}

    assert branch2[c4]["kind"] == "TestGazCar"
    assert branch2[c4]["action"] == "removed"
    assert branch2[c4]["summary"] == {"added": 0, "removed": 5, "updated": 0}
    assert branch2[c4]["elements"]["owner"]["peer"]["previous"]["id"] == p2

    assert branch2[p2]["display_label"] == "Jane"
    assert branch2[p2]["kind"] == "TestPerson"
    assert branch2[p2]["action"] == "updated"
    assert branch2[p2]["summary"] == {"added": 0, "removed": 1, "updated": 0}
    assert branch2[p2]["elements"]["cars"]["peers"][0]["peer"]["id"] == c4
    assert branch2[p2]["elements"]["cars"]["peers"][0]["peer"]["kind"] == "GazCar"

    assert branch2[r1]["kind"] == "CoreRepository"
    assert branch2[r1]["action"] == "updated"
    assert branch2[r1]["summary"] == {"added": 0, "removed": 0, "updated": 1}
    assert branch2[r1]["elements"]["commit"]["value"]["value"]["new"] == "dddddddddd"
    assert branch2[r1]["elements"]["commit"]["value"]["value"]["previous"] == "bbbbbbbbbbbbbbb"  # FIXME
    assert (
        branch2[r1]["elements"]["commit"]["value"]["changed_at"]
        == car_person_data_generic_diff["time21"].to_iso8601_string()
    )


async def test_diff_data_endpoint_branch_time_from_to(session, client, client_headers, car_person_data_generic_diff):
    time0 = car_person_data_generic_diff["time0"]
    time20 = car_person_data_generic_diff["time20"]

    c1 = car_person_data_generic_diff["c1"]
    p1 = car_person_data_generic_diff["p1"]
    p3 = car_person_data_generic_diff["p3"]
    r1 = car_person_data_generic_diff["r1"]

    with client:
        response = client.get(
            f"/diff/data?branch=branch2&branch_only=true&time_from={time0.to_iso8601_string()}&time_to={time20.to_iso8601_string()}",
            headers=client_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert list(data.keys()) == ["branch2"]

    branch2 = {node["id"]: node for node in data["branch2"]}

    assert branch2[p1]["display_label"] == "John"
    assert branch2[p1]["kind"] == "TestPerson"
    assert branch2[p1]["action"] == "updated"
    assert branch2[p1]["summary"] == {"added": 0, "removed": 1, "updated": 0}
    assert branch2[p1]["elements"]["cars"]["peers"][0]["peer"]["id"] == c1
    assert branch2[p1]["elements"]["cars"]["peers"][0]["peer"]["kind"] == "TestElectricCar"

    assert branch2[p3]["display_label"] == "Bill"
    assert branch2[p3]["action"] == "added"
    assert branch2[p3]["summary"] == {"added": 3, "removed": 0, "updated": 0}
    assert branch2[p3]["elements"]["cars"]["peers"][0]["peer"]["id"] == c1
    assert len(branch2[p3]["elements"]["name"]["properties"]) == 2

    assert branch2[c1]["kind"] == "TestElectricCar"
    assert branch2[c1]["action"] == "updated"
    assert branch2[c1]["summary"] == {"added": 0, "removed": 0, "updated": 1}
    assert branch2[c1]["elements"]["owner"]["peer"]["new"]["id"] == p3
    assert branch2[c1]["elements"]["owner"]["peer"]["previous"]["id"] == p1

    assert branch2[r1]["kind"] == "CoreRepository"
    assert branch2[r1]["action"] == "updated"
    assert branch2[r1]["summary"] == {"added": 0, "removed": 0, "updated": 1}
    assert branch2[r1]["elements"]["commit"]["value"]["value"]["new"] == "bbbbbbbbbbbbbbb"
    # assert branch2[r1]["elements"]["commit"]["value"]["value"]['previous'] == "aaaaaaaaa" FIXME
    assert (
        branch2[r1]["elements"]["commit"]["value"]["changed_at"]
        == car_person_data_generic_diff["time12"].to_iso8601_string()
    )


async def test_diff_data_endpoint_with_main_default(session, client, client_headers, car_person_data_generic_diff):
    c2 = car_person_data_generic_diff["c2"]
    p1 = car_person_data_generic_diff["p1"]

    with client:
        response = client.get(
            "/diff/data?branch=branch2&branch_only=false",
            headers=client_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert sorted(data.keys()) == ["branch2", "main"]
    assert len(data["branch2"]) == 5
    assert len(data["main"]) == 2

    # branch2 = { node["id"]: node for node in data["branch2"] }
    main = {node["id"]: node for node in data["main"]}

    assert main[p1]["kind"] == "TestPerson"
    assert main[p1]["action"] == "updated"
    assert main[p1]["summary"] == {"added": 0, "removed": 0, "updated": 1}
    assert main[p1]["elements"]["height"]["value"]["value"]["new"] == 120
    assert main[p1]["elements"]["height"]["value"]["value"]["previous"] == 180

    assert main[c2]["kind"] == "TestElectricCar"
    assert main[c2]["action"] == "updated"
    assert main[c2]["summary"] == {"added": 0, "removed": 0, "updated": 1}
    assert main[c2]["elements"]["nbr_seats"]["value"]["value"]["new"] == 4
    assert main[c2]["elements"]["nbr_seats"]["value"]["value"]["previous"] == 2


async def test_diff_data_endpoint_with_main_time_from(session, client, client_headers, car_person_data_generic_diff):
    time20 = car_person_data_generic_diff["time20"]

    c2 = car_person_data_generic_diff["c2"]
    c4 = car_person_data_generic_diff["c4"]
    p2 = car_person_data_generic_diff["p2"]
    r1 = car_person_data_generic_diff["r1"]

    with client:
        response = client.get(
            f"/diff/data?branch=branch2&branch_only=false&time_from={time20.to_iso8601_string()}",
            headers=client_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert sorted(data.keys()) == ["branch2", "main"]

    branch2 = {node["id"]: node for node in data["branch2"]}
    main = {node["id"]: node for node in data["main"]}

    assert main[c2]["kind"] == "TestElectricCar"
    assert main[c2]["action"] == "updated"
    assert main[c2]["summary"] == {"added": 0, "removed": 0, "updated": 1}
    assert main[c2]["elements"]["nbr_seats"]["value"]["value"]["new"] == 4
    assert main[c2]["elements"]["nbr_seats"]["value"]["value"]["previous"] == 2

    assert branch2[c4]["kind"] == "TestGazCar"
    assert branch2[c4]["action"] == "removed"
    assert branch2[c4]["summary"] == {"added": 0, "removed": 5, "updated": 0}
    assert branch2[c4]["elements"]["owner"]["peer"]["previous"]["id"] == p2

    assert branch2[p2]["display_label"] == "Jane"
    assert branch2[p2]["kind"] == "TestPerson"
    assert branch2[p2]["action"] == "updated"
    assert branch2[p2]["summary"] == {"added": 0, "removed": 1, "updated": 0}
    assert branch2[p2]["elements"]["cars"]["peers"][0]["peer"]["id"] == c4
    assert branch2[p2]["elements"]["cars"]["peers"][0]["peer"]["kind"] == "TestGazCar"

    assert branch2[r1]["kind"] == "CoreRepository"
    assert branch2[r1]["action"] == "updated"
    assert branch2[r1]["summary"] == {"added": 0, "removed": 0, "updated": 1}
    assert branch2[r1]["elements"]["commit"]["value"]["value"]["new"] == "dddddddddd"
    # assert branch2[r1]["elements"]["commit"]["value"]["value"]['previous'] == "bbbbbbbbbbbbbbb" FIXME
    assert (
        branch2[r1]["elements"]["commit"]["value"]["changed_at"]
        == car_person_data_generic_diff["time21"].to_iso8601_string()
    )


async def test_diff_data_endpoint_with_main_time_from_to(session, client, client_headers, car_person_data_generic_diff):
    time0 = car_person_data_generic_diff["time0"]
    time20 = car_person_data_generic_diff["time20"]

    c1 = car_person_data_generic_diff["c1"]
    p1 = car_person_data_generic_diff["p1"]
    p3 = car_person_data_generic_diff["p3"]
    r1 = car_person_data_generic_diff["r1"]

    with client:
        response = client.get(
            f"/diff/data?branch=branch2&branch_only=false&time_from={time0.to_iso8601_string()}&time_to={time20.to_iso8601_string()}",
            headers=client_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert sorted(data.keys()) == ["branch2", "main"]

    branch2 = {node["id"]: node for node in data["branch2"]}
    main = {node["id"]: node for node in data["main"]}

    # assert branch2[p1]["display_label"] == "John"
    # assert branch2[p1]["kind"] == "Person"
    # assert branch2[p1]["action"] == "updated"
    # assert branch2[p1]["summary"] == {'added': 0, 'removed': 1, 'updated': 0}
    # assert branch2[p1]["elements"]["cars"]["peers"][0]["peer"]["id"] == c1
    # assert branch2[p1]["elements"]["cars"]["peers"][0]["peer"]["kind"] == "ElectricCar"

    assert branch2[p3]["display_label"] == "Bill"
    assert branch2[p3]["action"] == "added"
    assert branch2[p3]["summary"] == {"added": 3, "removed": 0, "updated": 0}
    assert branch2[p3]["elements"]["cars"]["peers"][0]["peer"]["id"] == c1
    assert len(branch2[p3]["elements"]["name"]["properties"]) == 2

    assert branch2[c1]["kind"] == "TestElectricCar"
    assert branch2[c1]["action"] == "updated"
    assert branch2[c1]["summary"] == {"added": 0, "removed": 0, "updated": 1}
    assert branch2[c1]["elements"]["owner"]["peer"]["new"]["id"] == p3
    assert branch2[c1]["elements"]["owner"]["peer"]["previous"]["id"] == p1

    assert branch2[r1]["kind"] == "CoreRepository"
    assert branch2[r1]["action"] == "updated"
    assert branch2[r1]["summary"] == {"added": 0, "removed": 0, "updated": 1}
    assert branch2[r1]["elements"]["commit"]["value"]["value"]["new"] == "bbbbbbbbbbbbbbb"
    # assert branch2[r1]["elements"]["commit"]["value"]["value"]['previous'] == "aaaaaaaaa" FIXME
    assert (
        branch2[r1]["elements"]["commit"]["value"]["changed_at"]
        == car_person_data_generic_diff["time12"].to_iso8601_string()
    )

    assert main[p1]["kind"] == "TestPerson"
    assert main[p1]["action"] == "updated"
    assert main[p1]["summary"] == {"added": 0, "removed": 0, "updated": 1}
    assert main[p1]["elements"]["height"]["value"]["value"]["new"] == 120
    assert main[p1]["elements"]["height"]["value"]["value"]["previous"] == 180
