from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node


async def test_diff_data_endpoint(session, client, client_headers, default_branch, car_person_data):
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
            "/diff/data?branch=branch2",
            headers=client_headers,
        )

    assert response.status_code == 200
    assert response.json() is not None

    breakpoint()
