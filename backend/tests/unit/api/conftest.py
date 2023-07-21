from typing import Dict

import pendulum
import pytest
from fastapi.testclient import TestClient

from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node


@pytest.fixture
def client():
    # In order to mock some methods later we can't load app by default because it will automatically load all import in main.py as well
    from infrahub.api.main import app

    return TestClient(app)


@pytest.fixture
def client_headers():
    return {"Authorization": "Token XXXX"}


@pytest.fixture
def admin_headers():
    return {"X-INFRAHUB-KEY": "admin-security"}


@pytest.fixture
async def car_person_data(session, register_core_models_schema, car_person_schema, first_account) -> Dict[str, Node]:
    p1 = await Node.init(session=session, schema="TestPerson")
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)
    p2 = await Node.init(session=session, schema="TestPerson")
    await p2.new(session=session, name="Jane", height=170)
    await p2.save(session=session)
    c1 = await Node.init(session=session, schema="TestCar")
    await c1.new(session=session, name="volt", nbr_seats=3, is_electric=True, owner=p1)
    await c1.save(session=session)
    c2 = await Node.init(session=session, schema="TestCar")
    await c2.new(session=session, name="bolt", nbr_seats=2, is_electric=True, owner=p1)
    await c2.save(session=session)
    c3 = await Node.init(session=session, schema="TestCar")
    await c3.new(session=session, name="nolt", nbr_seats=4, is_electric=True, owner=p2)
    await c3.save(session=session)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    name {
                        value
                    }
                    cars {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """

    q1 = await Node.init(session=session, schema="CoreGraphQLQuery")
    await q1.new(session=session, name="query01", query=query)
    await q1.save(session=session)

    r1 = await Node.init(session=session, schema="CoreRepository")
    await r1.new(session=session, name="repo01", location="git@github.com:user/repo01.git")
    await r1.save(session=session)

    return {
        "p1": p1,
        "p2": p2,
        "c1": c1,
        "c2": c2,
        "c3": c3,
        "q1": q1,
        "r1": r1,
    }


@pytest.fixture
async def car_person_data_diff(session, default_branch, car_person_data, first_account):
    branch2 = await create_branch(branch_name="branch2", session=session)

    # Time post Branch Creation
    time0 = pendulum.now(tz="UTC")

    persons_list = await NodeManager.query(session=session, schema="Person", branch=branch2)
    persons = {item.name.value: item for item in persons_list}

    repos_list = await NodeManager.query(session=session, schema="Repository", branch=branch2)
    repos = {item.name.value: item for item in repos_list}

    cars_list = await NodeManager.query(session=session, schema="Car", branch=branch2)
    cars = {item.name.value: item for item in cars_list}

    # Add a new Person P3 in Branch2 and assign him as the owner of C1
    p3 = await Node.init(session=session, schema="Person", branch=branch2)
    await p3.new(session=session, name="Bill", height=160)
    await p3.save(session=session)
    persons["Bill"] = p3

    await cars["volt"].owner.update(data=p3, session=session)
    await cars["volt"].save(session=session)

    # Update P1 height in main
    p1 = await NodeManager.get_one(id=persons["John"].id, session=session)
    p1.height.value = 120
    await p1.save(session=session)

    # Time in-between the 2 batch of changes
    time1 = pendulum.now(tz="UTC")

    # Update Repo 01 in Branch2
    repo01 = repos["repo01"]
    repo01.commit.value = "dddddddddd"
    await repo01.save(session=session)

    # Update C2 main
    cars_list_main = await NodeManager.query(session=session, schema="Car", branch=default_branch)
    cars_main = {item.name.value: item for item in cars_list_main}

    cars_main["bolt"].nbr_seats.value = 4
    await cars_main["bolt"].save(session=session)

    # Time After the changes
    time2 = pendulum.now(tz="UTC")

    params = {
        "branch": branch2,
        "time0": time0,
        "time1": time1,
        "time2": time2,
    }

    return params


@pytest.fixture
async def car_person_data_generic(session, register_core_models_schema, car_person_schema_generics):
    p1 = await Node.init(session=session, schema="TestPerson")
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)
    p2 = await Node.init(session=session, schema="TestPerson")
    await p2.new(session=session, name="Jane", height=170)
    await p2.save(session=session)
    c1 = await Node.init(session=session, schema="TestElectricCar")
    await c1.new(session=session, name="volt", nbr_seats=3, nbr_engine=4, owner=p1)
    await c1.save(session=session)
    c2 = await Node.init(session=session, schema="TestElectricCar")
    await c2.new(session=session, name="bolt", nbr_seats=2, nbr_engine=2, owner=p1)
    await c2.save(session=session)
    c3 = await Node.init(session=session, schema="TestGazCar")
    await c3.new(session=session, name="nolt", nbr_seats=4, mpg=25, owner=p2)
    await c3.save(session=session)
    c4 = await Node.init(session=session, schema="TestGazCar")
    await c4.new(session=session, name="focus", nbr_seats=5, mpg=30, owner=p2)
    await c4.save(session=session)

    query = """
    query {
        TestPerson {
            name {
                value
            }
            cars {
                name {
                    value
                }
            }
        }
    }
    """

    q1 = await Node.init(session=session, schema="CoreGraphQLQuery")
    await q1.new(session=session, name="query01", query=query)
    await q1.save(session=session)

    r1 = await Node.init(session=session, schema="CoreRepository")
    await r1.new(session=session, name="repo01", location="git@github.com:user/repo01.git", commit="aaaaaaaaa")
    await r1.save(session=session)

    return {
        "p1": p1,
        "p2": p2,
        "c1": c1,
        "c2": c2,
        "c3": c3,
        "q1": q1,
        "r1": r1,
    }


@pytest.fixture
async def car_person_data_generic_diff(session, default_branch, car_person_data_generic, first_account):
    branch2 = await create_branch(branch_name="branch2", session=session)

    # Time After Creation of branch2
    time0 = pendulum.now(tz="UTC")

    persons_list = await NodeManager.query(session=session, schema="TestPerson", branch=branch2)
    persons = {item.name.value: item for item in persons_list}

    repos_list = await NodeManager.query(session=session, schema="CoreRepository", branch=branch2)
    repos = {item.name.value: item for item in repos_list}

    ecars_list = await NodeManager.query(session=session, schema="TestElectricCar", branch=branch2)
    ecars = {item.name.value: item for item in ecars_list}

    gcars_list = await NodeManager.query(session=session, schema="TestGazCar", branch=branch2)
    gcars = {item.name.value: item for item in gcars_list}

    # Add a new Person P3 in Branch2 and assign him as the owner of C1
    time10 = pendulum.now(tz="UTC")
    p3 = await Node.init(session=session, schema="TestPerson", branch=branch2)
    await p3.new(session=session, name="Bill", height=160)
    await p3.save(session=session, at=time10)
    persons["Bill"] = p3

    time11 = pendulum.now(tz="UTC")
    await ecars["volt"].owner.update(data=p3, session=session)
    await ecars["volt"].save(session=session, at=time11)

    # Update Repo 01 in Branch2 a first time
    time12 = pendulum.now(tz="UTC")
    repo01 = repos["repo01"]
    repo01.commit.value = "bbbbbbbbbbbbbbb"
    await repo01.save(session=session, at=time12)

    # Update P1 height in main
    time13 = pendulum.now(tz="UTC")
    p1 = await NodeManager.get_one(id=persons["John"].id, session=session)
    p1.height.value = 120
    await p1.save(session=session, at=time13)

    # Time in-between the 2 batch of changes
    time20 = pendulum.now(tz="UTC")

    # Update Repo 01 in Branch2 a second time
    time21 = pendulum.now(tz="UTC")
    repo01 = repos["repo01"]
    repo01.commit.value = "dddddddddd"
    await repo01.save(session=session, at=time21)

    # Delete C4 in Branch2
    await gcars["focus"].delete(session=session)

    # Update C2 main
    ecars_list_main = await NodeManager.query(session=session, schema="TestElectricCar", branch=default_branch)
    ecars_main = {item.name.value: item for item in ecars_list_main}

    ecars_main["bolt"].nbr_seats.value = 4
    await ecars_main["bolt"].save(session=session)

    # Time After the changes
    time30 = pendulum.now(tz="UTC")

    params = {
        "branch": branch2,
        "time0": time0,
        "time10": time10,
        "time11": time11,
        "time12": time12,
        "time13": time13,
        "time20": time20,
        "time21": time21,
        "time30": time30,
        "c1": ecars["volt"].id,
        "c2": ecars["bolt"].id,
        "c3": gcars["nolt"].id,
        "c4": gcars["focus"].id,
        "p1": persons["John"].id,
        "p2": persons["Jane"].id,
        "p3": p3.id,
        "r1": repo01.id,
    }

    return params
