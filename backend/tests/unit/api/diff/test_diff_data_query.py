from infrahub.core import registry
from infrahub.core.constants import DiffAction
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase


async def test_diff_data_add_node_on_this_branch(db: InfrahubDatabase, client, client_headers, car_person_schema):
    branch2 = await create_branch("branch2", db=db)
    person_schema = registry.schema.get(name="TestPerson", branch=branch2)
    person = await Node.init(schema=person_schema, db=db, branch=branch2)
    await person.new(db=db, name="Guy")
    await person.save(db=db)

    with client:
        response = client.get(
            "/api/diff/data?branch=branch2",
            headers=client_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert "diffs" in data
    diffs = data["diffs"]

    assert len(diffs) == 1
    assert diffs[0]["kind"] == "TestPerson"
    assert diffs[0]["id"] == person.id
    assert diffs[0]["action"] == {"branch2": DiffAction.ADDED.value}
    assert diffs[0]["display_label"] == {"branch2": "Guy"}
    assert diffs[0]["elements"]["name"]["change"]["action"] == DiffAction.ADDED.value


async def test_diff_data_add_node_on_another_branch(
    db: InfrahubDatabase, default_branch, client, client_headers, car_person_schema
):
    await create_branch("branch2", db=db)

    person_schema = registry.schema.get(name="TestPerson", branch=default_branch)
    person = await Node.init(schema=person_schema, db=db, branch=default_branch)
    await person.new(db=db, name="Guy")
    await person.save(db=db)

    with client:
        response = client.get(
            "/api/diff/data?branch=branch2",
            headers=client_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert "diffs" in data
    diffs = data["diffs"]

    assert len(diffs) == 0
