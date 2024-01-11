from typing import Dict

import pendulum
import pytest
from fastapi.testclient import TestClient

from infrahub import config
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase


@pytest.fixture
def client():
    # In order to mock some methods later we can't load app by default because it will automatically load all import in main.py as well
    from infrahub.server import app

    return TestClient(app)


@pytest.fixture
def client_headers():
    return {"Authorization": "Token XXXX"}


@pytest.fixture
def admin_headers():
    return {"X-INFRAHUB-KEY": "admin-security"}


@pytest.fixture
def rpc_bus(helper):
    original = config.OVERRIDE.message_bus
    bus = helper.get_message_bus_rpc()
    config.OVERRIDE.message_bus = bus
    yield bus
    config.OVERRIDE.message_bus = original


@pytest.fixture
async def car_person_data(
    db: InfrahubDatabase, register_core_models_schema, car_person_schema, first_account
) -> Dict[str, Node]:
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)
    p2 = await Node.init(db=db, schema="TestPerson")
    await p2.new(db=db, name="Jane", height=170)
    await p2.save(db=db)
    c1 = await Node.init(db=db, schema="TestCar")
    await c1.new(db=db, name="volt", nbr_seats=3, is_electric=True, owner=p1)
    await c1.save(db=db)
    c2 = await Node.init(db=db, schema="TestCar")
    await c2.new(db=db, name="bolt", nbr_seats=2, is_electric=True, owner=p1)
    await c2.save(db=db)
    c3 = await Node.init(db=db, schema="TestCar")
    await c3.new(db=db, name="nolt", nbr_seats=4, is_electric=True, owner=p2)
    await c3.save(db=db)

    query1 = """
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

    query2 = """
    query($person: String!) {
        TestPerson(name__value: $person) {
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """

    q1 = await Node.init(db=db, schema="CoreGraphQLQuery")
    await q1.new(db=db, name="query01", query=query1)
    await q1.save(db=db)

    q2 = await Node.init(db=db, schema="CoreGraphQLQuery")
    await q2.new(db=db, name="query02", query=query2)
    await q2.save(db=db)

    r1 = await Node.init(db=db, schema="CoreRepository")
    await r1.new(
        db=db,
        name="repo01",
        location="git@github.com:user/repo01.git",
        commit="36be6d233059b70d572a5bdb1a85bde531691ece",
    )
    await r1.save(db=db)

    return {
        "p1": p1,
        "p2": p2,
        "c1": c1,
        "c2": c2,
        "c3": c3,
        "q1": q1,
        "q2": q2,
        "r1": r1,
    }


@pytest.fixture
async def car_person_data_diff(db: InfrahubDatabase, default_branch, car_person_data, first_account):
    branch2 = await create_branch(branch_name="branch2", db=db)

    # Time post Branch Creation
    time0 = pendulum.now(tz="UTC")

    persons_list = await NodeManager.query(db=db, schema="Person", branch=branch2)
    persons = {item.name.value: item for item in persons_list}

    repos_list = await NodeManager.query(db=db, schema="Repository", branch=branch2)
    repos = {item.name.value: item for item in repos_list}

    cars_list = await NodeManager.query(db=db, schema="Car", branch=branch2)
    cars = {item.name.value: item for item in cars_list}

    # Add a new Person P3 in Branch2 and assign him as the owner of C1
    p3 = await Node.init(db=db, schema="Person", branch=branch2)
    await p3.new(db=db, name="Bill", height=160)
    await p3.save(db=db)
    persons["Bill"] = p3

    await cars["volt"].owner.update(data=p3, db=db)
    await cars["volt"].save(db=db)

    # Update P1 height in main
    p1 = await NodeManager.get_one(id=persons["John"].id, db=db)
    p1.height.value = 120
    await p1.save(db=db)

    # Time in-between the 2 batch of changes
    time1 = pendulum.now(tz="UTC")

    # Update Repo 01 in Branch2
    repo01 = repos["repo01"]
    repo01.commit.value = "dddddddddd"
    await repo01.save(db=db)

    # Update C2 main
    cars_list_main = await NodeManager.query(db=db, schema="Car", branch=default_branch)
    cars_main = {item.name.value: item for item in cars_list_main}

    cars_main["bolt"].nbr_seats.value = 4
    await cars_main["bolt"].save(db=db)

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
async def car_person_data_generic_diff(db: InfrahubDatabase, default_branch, car_person_data_generic, first_account):
    branch2 = await create_branch(branch_name="branch2", db=db)

    # Time After Creation of branch2
    time0 = pendulum.now(tz="UTC")

    persons_list = await NodeManager.query(db=db, schema="TestPerson", branch=branch2)
    persons = {item.name.value: item for item in persons_list}

    repos_list = await NodeManager.query(db=db, schema="CoreRepository", branch=branch2)
    repos = {item.name.value: item for item in repos_list}

    ecars_list = await NodeManager.query(db=db, schema="TestElectricCar", branch=branch2)
    ecars = {item.name.value: item for item in ecars_list}

    gcars_list = await NodeManager.query(db=db, schema="TestGazCar", branch=branch2)
    gcars = {item.name.value: item for item in gcars_list}

    # Add a new Person P3 in Branch2 and assign him as the owner of C1
    time10 = pendulum.now(tz="UTC")
    p3 = await Node.init(db=db, schema="TestPerson", branch=branch2)
    await p3.new(db=db, name="Bill", height=160)
    await p3.save(db=db, at=time10)
    persons["Bill"] = p3

    time11 = pendulum.now(tz="UTC")
    await ecars["volt"].owner.update(data=p3, db=db)
    await ecars["volt"].save(db=db, at=time11)

    # Update Repo 01 in Branch2 a first time
    time12 = pendulum.now(tz="UTC")
    repo01 = repos["repo01"]
    repo01.commit.value = "bbbbbbbbbbbbbbb"
    repo01.description.value = "First change in branch"
    await repo01.save(db=db, at=time12)

    # Update P1 height in main
    time13 = pendulum.now(tz="UTC")
    p1 = await NodeManager.get_one(id=persons["John"].id, db=db)
    p1.height.value = 120
    await p1.save(db=db, at=time13)

    # Time in-between the 2 batch of changes
    time20 = pendulum.now(tz="UTC")

    # Update Repo 01 in Branch2 a second time
    time21 = pendulum.now(tz="UTC")
    repo01 = repos["repo01"]
    repo01.commit.value = "dddddddddd"
    repo01.description.value = "Second change in branch"
    await repo01.save(db=db, at=time21)

    # Delete C4 in Branch2
    await gcars["focus"].delete(db=db)

    # Update C2 main
    ecars_list_main = await NodeManager.query(db=db, schema="TestElectricCar", branch=default_branch)
    ecars_main = {item.name.value: item for item in ecars_list_main}

    ecars_main["bolt"].nbr_seats.value = 4
    await ecars_main["bolt"].save(db=db)

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


@pytest.fixture
async def car_person_data_artifact_diff(db: InfrahubDatabase, default_branch, car_person_data_generic_diff):
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

    q1 = await Node.init(db=db, schema="CoreGraphQLQuery")
    await q1.new(db=db, name="query01", query=query)
    await q1.save(db=db)

    r1 = await Node.init(db=db, schema="CoreRepository")
    await r1.new(db=db, name="repo01", location="git@github.com:user/repo01.git", commit="aaaaaaaaa")
    await r1.save(db=db)

    g1 = await Node.init(db=db, schema="CoreStandardGroup")
    await g1.new(db=db, name="group1", members=[car_person_data_generic_diff["c1"], car_person_data_generic_diff["c2"]])
    await g1.save(db=db)

    t1 = await Node.init(db=db, schema="CoreTransformPython")
    await t1.new(
        db=db,
        name="transform01",
        query=str(q1.id),
        url="mytransform",
        repository=str(r1.id),
        file_path="transform01.py",
        class_name="Transform01",
        rebase=False,
    )
    await t1.save(db=db)

    ad1 = await Node.init(db=db, schema="CoreArtifactDefinition")
    await ad1.new(
        db=db,
        name="artifactdef01",
        targets=g1,
        transformation=t1,
        content_type="application/json",
        artifact_name="myartifact",
        parameters='{"name": "name__value"}',
    )
    await ad1.save(db=db)

    art1 = await Node.init(db=db, schema="CoreArtifact")
    await art1.new(
        db=db,
        name="myyartifact",
        definition=ad1,
        status="Ready",
        object=car_person_data_generic_diff["c1"],
        storage_id="8caf6f89-073f-4173-aa4b-f50e1309f03c",
        checksum="60d39063c26263353de24e1b913e1e1c",
        content_type="application/json",
    )
    await art1.save(db=db)

    branch3 = await create_branch(branch_name="branch3", db=db)

    artifacts = await NodeManager.get_many(db=db, ids=[art1.id], branch=branch3)

    artifacts[art1.id].storage_id.value = "azertyui-073f-4173-aa4b-f50e1309f03c"
    artifacts[art1.id].checksum.value = "zxcv9063c26263353de24e1b911z1x2c3v"
    await artifacts[art1.id].save(db=db)

    art2 = await Node.init(db=db, schema="CoreArtifact", branch=branch3)
    await art2.new(
        db=db,
        name="myyartifact",
        definition=ad1,
        status="Ready",
        object=car_person_data_generic_diff["c2"],
        storage_id="qwertyui-073f-4173-aa4b-f50e1309f03c",
        checksum="zxcv9063c26263353de24e1b913e1e1c",
        content_type="application/json",
    )
    await art2.save(db=db)

    art3_main = await Node.init(db=db, schema="CoreArtifact", branch=default_branch)
    await art3_main.new(
        db=db,
        name="myyartifact",
        definition=ad1,
        status="Ready",
        object=car_person_data_generic_diff["c3"],
        storage_id="mnbvcxza-073f-4173-aa4b-f50e1309f03c",
        checksum="poiuytrewq9063c26263353de24e1b913e1e1c",
        content_type="application/json",
    )
    await art3_main.save(db=db)

    art3_branch = await Node.init(db=db, schema="CoreArtifact", branch=branch3)
    await art3_branch.new(
        db=db,
        name="myyartifact",
        definition=ad1,
        status="Ready",
        object=car_person_data_generic_diff["c3"],
        storage_id="lkjhgfds-073f-4173-aa4b-f50e1309f03c",
        checksum="nhytgbvfredc9063c26263353de24e1b913e1e1c",
        content_type="application/json",
    )
    await art3_branch.save(db=db)

    car_person_data_generic_diff["branch3"] = branch3
    car_person_data_generic_diff["art1"] = art1.id
    car_person_data_generic_diff["art2"] = art2.id
    car_person_data_generic_diff["art3"] = art3_branch.id

    return car_person_data_generic_diff


@pytest.fixture
async def data_diff_attribute(db: InfrahubDatabase, default_branch, car_person_data_generic, first_account):
    branch2 = await create_branch(branch_name="branch2", db=db)

    # Time After Creation of branch2
    time0 = pendulum.now(tz="UTC")

    persons_list = await NodeManager.query(db=db, schema="TestPerson", branch=branch2)
    persons = {item.name.value: item for item in persons_list}

    repos_list = await NodeManager.query(db=db, schema="CoreRepository", branch=branch2)
    repos = {item.name.value: item for item in repos_list}

    ecars_list = await NodeManager.query(db=db, schema="TestElectricCar", branch=branch2)
    ecars = {item.name.value: item for item in ecars_list}

    gcars_list = await NodeManager.query(db=db, schema="TestGazCar", branch=branch2)
    gcars = {item.name.value: item for item in gcars_list}

    # Update Repo 01 in Branch2 a first time
    time12 = pendulum.now(tz="UTC")
    repo01 = repos["repo01"]
    repo01.commit.value = "bbbbbbbbbbbbbbb"
    repo01.description.value = "First update in Branch"
    await repo01.save(db=db, at=time12)

    # Update P1 height in main
    time13 = pendulum.now(tz="UTC")
    p1 = await NodeManager.get_one(id=persons["John"].id, db=db)
    p1.height.value = 120
    await p1.save(db=db, at=time13)

    # Time in-between the 2 batch of changes
    time20 = pendulum.now(tz="UTC")

    # Update Repo 01 in Branch2 a second time
    time21 = pendulum.now(tz="UTC")
    repo01 = repos["repo01"]
    repo01.commit.value = "dddddddddd"
    repo01.description.value = "Second update in Branch"
    await repo01.save(db=db, at=time21)

    # Update C2 main
    ecars_list_main = await NodeManager.query(db=db, schema="TestElectricCar", branch=default_branch)
    ecars_main = {item.name.value: item for item in ecars_list_main}

    ecars_main["bolt"].nbr_seats.value = 4
    await ecars_main["bolt"].save(db=db)

    # Time After the changes
    time30 = pendulum.now(tz="UTC")

    params = {
        "branch": branch2,
        "time0": time0,
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
        "r1": repo01.id,
    }

    return params


@pytest.fixture
async def data_conflict_attribute(db: InfrahubDatabase, default_branch, car_person_data_generic, first_account):
    branch2 = await create_branch(branch_name="branch2", db=db)

    # Time After Creation of branch2
    time0 = pendulum.now(tz="UTC")

    persons_list_branch = await NodeManager.query(db=db, schema="TestPerson", branch=branch2)
    persons_branch = {item.name.value: item for item in persons_list_branch}

    persons_list_main = await NodeManager.query(db=db, schema="TestPerson", branch=default_branch)
    persons_main = {item.name.value: item for item in persons_list_main}

    repos_list_branch = await NodeManager.query(db=db, schema="CoreRepository", branch=branch2)
    repos_branch = {item.name.value: item for item in repos_list_branch}

    repos_list_main = await NodeManager.query(db=db, schema="CoreRepository", branch=default_branch)
    repos_main = {item.name.value: item for item in repos_list_main}

    # Update Repo 01 in Branch2 a first time
    time12 = pendulum.now(tz="UTC")
    repos_branch["repo01"].commit.value = "bbbbbbbbbbbbbbb"
    repos_branch["repo01"].description.value = "First update in Branch"
    await repos_branch["repo01"].save(db=db, at=time12)

    # Update P1 height in branch2
    time13 = pendulum.now(tz="UTC")
    persons_branch["John"].height.value = 666
    await persons_branch["John"].save(db=db, at=time13)

    # Update P1 height in main
    persons_main["John"].height.value = 120
    await persons_main["John"].save(db=db, at=time13)

    # Time in-between the 2 batch of changes
    time20 = pendulum.now(tz="UTC")

    # Update Repo 01 in Branch2 a second time
    time21 = pendulum.now(tz="UTC")
    repos_branch["repo01"].commit.value = "dddddddddd"
    repos_branch["repo01"].description.value = "Second update in Branch"
    await repos_branch["repo01"].save(db=db, at=time21)

    # Update Repo 01 in main
    time22 = pendulum.now(tz="UTC")
    repos_main["repo01"].commit.value = "mmmmmmmmmmmmm"
    repos_main["repo01"].description.value = "update in main"
    await repos_main["repo01"].save(db=db, at=time12)

    # Time After the changes
    time30 = pendulum.now(tz="UTC")

    params = {
        "branch": branch2,
        "time0": time0,
        "time12": time12,
        "time13": time13,
        "time20": time20,
        "time21": time21,
        "time22": time22,
        "time30": time30,
        "p1": persons_branch["John"].id,
        "p2": persons_branch["Jane"].id,
        "r1": repos_main["repo01"].id,
    }

    return params


@pytest.fixture
async def data_diff_relationship_one(db: InfrahubDatabase, default_branch, car_person_data_generic, first_account):
    # Set some values in C1 in Main before creating the branch
    time_minus1 = pendulum.now(tz="UTC")

    c1_main = await NodeManager.get_one_by_id_or_default_filter(
        db=db, id="volt", schema_name="TestElectricCar", branch=default_branch
    )

    p2_main = await NodeManager.get_one_by_id_or_default_filter(
        db=db, id="Jane", schema_name="TestPerson", branch=default_branch
    )

    await c1_main.previous_owner.update(data=p2_main, db=db)
    await c1_main.save(db=db, at=time_minus1)

    branch2 = await create_branch(branch_name="branch2", db=db)

    # Time After Creation of branch2
    time0 = pendulum.now(tz="UTC")

    persons_list = await NodeManager.query(db=db, schema="TestPerson", branch=branch2)
    persons = {item.name.value: item for item in persons_list}

    ecars_list = await NodeManager.query(db=db, schema="TestElectricCar", branch=branch2)
    ecars = {item.name.value: item for item in ecars_list}

    # Change previous owner of C1 from P1 to P2 in branch
    time11 = pendulum.now(tz="UTC")
    await ecars["volt"].previous_owner.update(data=persons["John"], db=db)
    await ecars["volt"].save(db=db, at=time11)

    # Time in-between the 2 batch of changes
    time20 = pendulum.now(tz="UTC")

    # Set previous owner for C2 in branch
    await ecars["bolt"].previous_owner.update(data=persons["Jane"], db=db)
    await ecars["bolt"].save(db=db, at=time20)

    # Time After the changes
    time30 = pendulum.now(tz="UTC")

    params = {
        "branch": branch2,
        "time0": time0,
        "time11": time11,
        "time20": time20,
        "time30": time30,
        "c1": ecars["volt"].id,
        "c2": ecars["bolt"].id,
        "p1": persons["John"].id,
        "p2": persons["Jane"].id,
    }

    return params


@pytest.fixture
async def data_conflict_relationship_one(db: InfrahubDatabase, default_branch, car_person_data_generic, first_account):
    # Set some values in C1 in Main before creating the branch
    time_minus1 = pendulum.now(tz="UTC")

    ecars_list_main = await NodeManager.query(db=db, schema="TestElectricCar", branch=default_branch)
    ecars_main = {item.name.value: item for item in ecars_list_main}

    persons_list_main = await NodeManager.query(db=db, schema="TestPerson", branch=default_branch)
    persons_main = {item.name.value: item for item in persons_list_main}

    await ecars_main["volt"].previous_owner.update(data=persons_main["Jane"], db=db)
    await ecars_main["volt"].save(db=db, at=time_minus1)

    branch2 = await create_branch(branch_name="branch2", db=db)

    # Time After Creation of branch2
    time0 = pendulum.now(tz="UTC")

    persons_list_branch = await NodeManager.query(db=db, schema="TestPerson", branch=branch2)
    persons_branch = {item.name.value: item for item in persons_list_branch}

    ecars_list_branch = await NodeManager.query(db=db, schema="TestElectricCar", branch=branch2)
    ecars_branch = {item.name.value: item for item in ecars_list_branch}

    # Change previous owner of C1 from P1 to P2 in branch
    time11 = pendulum.now(tz="UTC")
    await ecars_branch["volt"].previous_owner.update(data=persons_branch["John"], db=db)
    await ecars_branch["volt"].save(db=db, at=time11)

    # Change previous owner of C1 from P1 to Null in main
    time12 = pendulum.now(tz="UTC")
    await ecars_main["volt"].previous_owner.update(data=None, db=db)
    await ecars_main["volt"].save(db=db, at=time12)

    # Time in-between the 2 batch of changes
    time20 = pendulum.now(tz="UTC")

    # Set previous owner for C2 in branch
    await ecars_branch["bolt"].previous_owner.update(data=persons_branch["Jane"], db=db)
    await ecars_branch["bolt"].save(db=db, at=time20)

    # Set previous owner for C2 in main
    time21 = pendulum.now(tz="UTC")

    await ecars_main["bolt"].previous_owner.update(data=persons_branch["John"], db=db)
    await ecars_main["bolt"].save(db=db, at=time21)

    # Time After the changes
    time30 = pendulum.now(tz="UTC")

    params = {
        "branch": branch2,
        "time0": time0,
        "time11": time11,
        "time12": time12,
        "time20": time20,
        "time21": time21,
        "time30": time30,
        "c1": ecars_branch["volt"].id,
        "c2": ecars_branch["bolt"].id,
        "p1": persons_branch["John"].id,
        "p2": persons_branch["Jane"].id,
    }

    return params


@pytest.fixture
async def data_relationship_many_base(db: InfrahubDatabase, default_branch, register_core_models_schema, first_account):
    red = await Node.init(db=db, schema="BuiltinTag")
    await red.new(db=db, name="red")
    await red.save(db=db)

    green = await Node.init(db=db, schema="BuiltinTag")
    await green.new(db=db, name="green")
    await green.save(db=db)

    blue = await Node.init(db=db, schema="BuiltinTag")
    await blue.new(db=db, name="blue")
    await blue.save(db=db)

    yellow = await Node.init(db=db, schema="BuiltinTag")
    await yellow.new(db=db, name="yellow")
    await yellow.save(db=db)

    orange = await Node.init(db=db, schema="BuiltinTag")
    await orange.new(db=db, name="orange")
    await orange.save(db=db)

    pink = await Node.init(db=db, schema="BuiltinTag")
    await pink.new(db=db, name="pink")
    await pink.save(db=db)

    org1 = await Node.init(db=db, schema="CoreOrganization")
    await org1.new(db=db, name="org1", tags=[red.id, green.id])
    await org1.save(db=db)

    org2 = await Node.init(db=db, schema="CoreOrganization")
    await org2.new(db=db, name="org2", tags=[red.id, blue.id, orange.id])
    await org2.save(db=db)

    org3 = await Node.init(db=db, schema="CoreOrganization")
    await org3.new(db=db, name="org3")
    await org3.save(db=db)

    return {
        "red": red,
        "green": green,
        "blue": blue,
        "yellow": yellow,
        "orange": orange,
        "pink": pink,
        "org1": org1,
        "org2": org2,
        "org3": org3,
    }


@pytest.fixture
async def data_diff_relationship_many(db: InfrahubDatabase, default_branch, data_relationship_many_base):
    red = data_relationship_many_base["red"]
    blue = data_relationship_many_base["blue"]
    data_relationship_many_base["green"]
    data_relationship_many_base["yellow"]
    orange = data_relationship_many_base["orange"]

    branch2 = await create_branch(branch_name="branch2", db=db)

    orgs_list_main = await NodeManager.query(db=db, schema="CoreOrganization", branch=default_branch)
    orgs_main = {item.name.value: item for item in orgs_list_main}
    orgs_list_branch = await NodeManager.query(db=db, schema="CoreOrganization", branch=branch2)
    orgs_branch = {item.name.value: item for item in orgs_list_branch}

    await orgs_main["org1"].tags.update(data=[red.id, blue.id], db=db)
    await orgs_main["org1"].save(db=db)

    await orgs_branch["org3"].tags.update(data=[red.id, orange.id], db=db)
    await orgs_branch["org3"].save(db=db)

    return data_relationship_many_base


@pytest.fixture
async def data_conflict_relationship_many(db: InfrahubDatabase, default_branch, data_relationship_many_base):
    red = data_relationship_many_base["red"]
    data_relationship_many_base["blue"]
    green = data_relationship_many_base["green"]
    data_relationship_many_base["yellow"]
    data_relationship_many_base["orange"]

    branch2 = await create_branch(branch_name="branch2", db=db)

    orgs_list_main = await NodeManager.query(db=db, schema="CoreOrganization", branch=default_branch)
    orgs_main = {item.name.value: item for item in orgs_list_main}
    orgs_list_branch = await NodeManager.query(db=db, schema="CoreOrganization", branch=branch2)
    orgs_branch = {item.name.value: item for item in orgs_list_branch}

    await orgs_main["org1"].tags.update(data=[], db=db)
    await orgs_main["org1"].save(db=db)

    await orgs_branch["org1"].tags.update(data=[{"id": red.id, "_relation__is_protected": True}, green.id], db=db)
    await orgs_branch["org1"].save(db=db)

    return data_relationship_many_base
