import pytest
from fast_depends import Provider
from fastapi.testclient import TestClient

from infrahub import config
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workers.dependencies import build_database, build_message_bus, build_workflow
from infrahub.workflows.initialization import setup_task_manager


@pytest.fixture
def client(dependency_provider: Provider, nats, redis):
    # In order to mock some methods later we can't load app by default because it will automatically load all import in main.py as well
    from infrahub.server import app

    async def _db(singleton: bool = True) -> InfrahubDatabase:
        return await build_database(singleton=False)

    with dependency_provider.scope(build_database, _db):
        yield TestClient(app)


@pytest.fixture
def client_headers():
    return {"Authorization": "Token XXXX"}


@pytest.fixture
def admin_headers():
    return {"X-INFRAHUB-KEY": "admin-security"}


@pytest.fixture
def rpc_bus(helper, dependency_provider):
    original = config.OVERRIDE.message_bus
    bus = helper.get_message_bus_rpc()
    config.OVERRIDE.message_bus = bus
    with dependency_provider.scope(build_message_bus, lambda: bus):
        yield bus
    config.OVERRIDE.message_bus = original


@pytest.fixture
async def workflow_local(dependency_provider):
    original = config.OVERRIDE.workflow
    workflow = WorkflowLocalExecution()
    await setup_task_manager()
    config.OVERRIDE.workflow = workflow
    with dependency_provider.scope(build_workflow, lambda: workflow):
        yield workflow
    config.OVERRIDE.workflow = original


@pytest.fixture
async def car_person_data(
    db: InfrahubDatabase, register_core_models_schema, car_person_schema, first_account
) -> dict[str, Node]:
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

    q1 = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
    await q1.new(db=db, name="query01", query=query1)
    await q1.save(db=db)

    q2 = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
    await q2.new(db=db, name="query02", query=query2)
    await q2.save(db=db)

    r1 = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
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
async def car_person_data_generic_diff(db: InfrahubDatabase, default_branch, car_person_data_generic, first_account):
    branch2 = await create_branch(branch_name="branch2", db=db)

    # Time After Creation of branch2
    time0 = Timestamp()

    persons_list = await NodeManager.query(db=db, schema="TestPerson", branch=branch2)
    persons = {item.name.value: item for item in persons_list}

    repos_list = await NodeManager.query(db=db, schema=InfrahubKind.REPOSITORY, branch=branch2)
    repos = {item.name.value: item for item in repos_list}

    ecars_list = await NodeManager.query(db=db, schema="TestElectricCar", branch=branch2)
    ecars = {item.name.value: item for item in ecars_list}

    gcars_list = await NodeManager.query(db=db, schema="TestGazCar", branch=branch2)
    gcars = {item.name.value: item for item in gcars_list}

    # Add a new Person P3 in Branch2 and assign him as the owner of C1
    time10 = Timestamp()
    p3 = await Node.init(db=db, schema="TestPerson", branch=branch2)
    await p3.new(db=db, name="Bill", height=160)
    await p3.save(db=db, at=time10)
    persons["Bill"] = p3

    time11 = Timestamp()
    await ecars["volt"].owner.update(data=p3, db=db)
    await ecars["volt"].save(db=db, at=time11)

    # Update Repo 01 in Branch2 a first time
    time12 = Timestamp()
    repo01 = repos["repo01"]
    repo01.commit.value = "bbbbbbbbbbbbbbb"
    repo01.description.value = "First change in branch"
    await repo01.save(db=db, at=time12)

    # Update P1 height in main
    time13 = Timestamp()
    p1 = await NodeManager.get_one(id=persons["John"].id, db=db)
    p1.height.value = 120
    await p1.save(db=db, at=time13)

    # Time in-between the 2 batch of changes
    time20 = Timestamp()

    # Update Repo 01 in Branch2 a second time
    time21 = Timestamp()
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
    time30 = Timestamp()

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

    q1 = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
    await q1.new(db=db, name="query01", query=query)
    await q1.save(db=db)

    r1 = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await r1.new(db=db, name="repo01", location="git@github.com:user/repo01.git", commit="aaaaaaaaa")
    await r1.save(db=db)

    g1 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g1.new(db=db, name="group1", members=[car_person_data_generic_diff["c1"], car_person_data_generic_diff["c2"]])
    await g1.save(db=db)

    t1 = await Node.init(db=db, schema="CoreTransformPython")
    await t1.new(
        db=db,
        name="transform01",
        query=str(q1.id),
        repository=str(r1.id),
        file_path="transform01.py",
        class_name="Transform01",
    )
    await t1.save(db=db)

    ad1 = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
    await ad1.new(
        db=db,
        name="artifactdef01",
        targets=g1,
        transformation=t1,
        content_type="application/json",
        artifact_name="myartifact",
        parameters={"value": {"name": "name__value"}},
    )
    await ad1.save(db=db)

    art1 = await Node.init(db=db, schema=InfrahubKind.ARTIFACT)
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

    art1_branch = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=branch3)
    await art1_branch.new(
        db=db,
        name="myyartifact",
        definition=ad1,
        status="Ready",
        object=car_person_data_generic_diff["c1"],
        storage_id="azertyui-073f-4173-aa4b-f50e1309f03c",
        checksum="zxcv9063c26263353de24e1b911z1x2c3v",
        content_type="application/json",
    )
    await art1_branch.save(db=db)

    art2 = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=branch3)
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

    art3_main = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=default_branch)
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

    art3_branch = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=branch3)
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
    car_person_data_generic_diff["art1"] = art1_branch.id
    car_person_data_generic_diff["art2"] = art2.id
    car_person_data_generic_diff["art3"] = art3_branch.id

    return car_person_data_generic_diff


@pytest.fixture
async def data_diff_attribute(db: InfrahubDatabase, default_branch, car_person_data_generic, first_account):
    branch2 = await create_branch(branch_name="branch2", db=db)

    # Time After Creation of branch2
    time0 = Timestamp()

    persons_list = await NodeManager.query(db=db, schema="TestPerson", branch=branch2)
    persons = {item.name.value: item for item in persons_list}

    repos_list = await NodeManager.query(db=db, schema=InfrahubKind.REPOSITORY, branch=branch2)
    repos = {item.name.value: item for item in repos_list}

    ecars_list = await NodeManager.query(db=db, schema="TestElectricCar", branch=branch2)
    ecars = {item.name.value: item for item in ecars_list}

    gcars_list = await NodeManager.query(db=db, schema="TestGazCar", branch=branch2)
    gcars = {item.name.value: item for item in gcars_list}

    # Update Repo 01 in Branch2 a first time
    time12 = Timestamp()
    repo01 = repos["repo01"]
    repo01.commit.value = "bbbbbbbbbbbbbbb"
    repo01.description.value = "First update in Branch"
    await repo01.save(db=db, at=time12)

    # Update P1 height in main
    time13 = Timestamp()
    p1 = await NodeManager.get_one(id=persons["John"].id, db=db)
    p1.height.value = 120
    await p1.save(db=db, at=time13)

    # Time in-between the 2 batch of changes
    time20 = Timestamp()

    # Update Repo 01 in Branch2 a second time
    time21 = Timestamp()
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
    time30 = Timestamp()

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
