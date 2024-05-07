import pytest
from deepdiff import DeepDiff

from infrahub.core.constants import NULL_VALUE, InfrahubKind
from infrahub.core.diff.payload_builder import get_display_labels, get_display_labels_per_kind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase


async def test_get_display_labels_per_kind(db: InfrahubDatabase, default_branch, car_person_data):
    persons_list = await NodeManager.query(db=db, schema="TestPerson", branch=default_branch)
    person_ids = [item.id for item in persons_list]
    display_labels = await get_display_labels_per_kind(
        kind="TestPerson", ids=person_ids, branch_name=default_branch.name, db=db
    )
    assert len(display_labels) == len(person_ids)


async def test_get_display_labels_per_kind_with_branch(db: InfrahubDatabase, default_branch, car_person_data):
    branch2 = await create_branch(branch_name="branch2", db=db)

    # Add a new Person
    p3 = await Node.init(db=db, schema="TestPerson", branch=branch2)
    await p3.new(db=db, name="Bill", height=160)
    await p3.save(db=db)

    persons_list = await NodeManager.query(db=db, schema="TestPerson", branch=branch2)
    person_ids = [item.id for item in persons_list]

    display_labels = await get_display_labels_per_kind(
        kind="TestPerson", ids=person_ids, branch_name=branch2.name, db=db
    )
    assert len(display_labels) == len(person_ids)


async def test_get_display_labels(db: InfrahubDatabase, default_branch, car_person_data):
    persons_list = await NodeManager.query(db=db, schema="TestPerson", branch=default_branch)
    person_ids = [item.id for item in persons_list]
    cars_list = await NodeManager.query(db=db, schema="TestCar", branch=default_branch)
    car_ids = [item.id for item in cars_list]

    display_labels = await get_display_labels(nodes={"main": {"TestPerson": person_ids, "TestCar": car_ids}}, db=db)
    assert len(display_labels["main"]) == len(car_ids) + len(person_ids)


async def test_get_display_labels_with_branch(db: InfrahubDatabase, default_branch, car_person_data):
    branch2 = await create_branch(branch_name="branch2", db=db)

    persons_list = await NodeManager.query(db=db, schema="TestPerson", branch=branch2)
    persons = {item.name.value: item for item in persons_list}

    repos_list = await NodeManager.query(db=db, schema=InfrahubKind.REPOSITORY, branch=branch2)
    repos = {item.name.value: item for item in repos_list}

    cars_list = await NodeManager.query(db=db, schema="TestCar", branch=branch2)
    cars = {item.name.value: item for item in cars_list}

    # Add a new Person
    p3 = await Node.init(db=db, schema="TestPerson", branch=branch2)
    await p3.new(db=db, name="Bill", height=160)
    await p3.save(db=db)
    persons["Bill"] = p3

    await cars["volt"].owner.update(data=p3, db=db)
    await cars["volt"].save(db=db)

    repo01 = repos["repo01"]
    repo01.commit.value = "dddddddddd"
    await repo01.save(db=db)

    # Update P1 height in main
    p1 = await NodeManager.get_one(id=persons["John"].id, db=db)
    p1.height.value = 120
    await p1.save(db=db)

    persons_list = await NodeManager.query(db=db, schema="TestPerson", branch=branch2)
    person_ids = [item.id for item in persons_list]
    cars_list = await NodeManager.query(db=db, schema="TestCar", branch=branch2)
    car_ids = [item.id for item in cars_list]

    display_labels = await get_display_labels(
        nodes={branch2.name: {"TestPerson": person_ids, "TestCar": car_ids}}, db=db
    )
    assert len(display_labels["branch2"]) == len(car_ids) + len(person_ids)


# ----------------------------------------------------------------------
# New API
# ----------------------------------------------------------------------


@pytest.fixture
async def r1_update_01(data_diff_attribute):
    r1 = data_diff_attribute["r1"]

    expected_response = {
        "kind": InfrahubKind.REPOSITORY,
        "id": r1,
        "path": f"data/{r1}",
        "elements": {
            "description": {
                "type": "Attribute",
                "name": "description",
                "path": f"data/{r1}/description",
                "change": {
                    "type": "Attribute",
                    "branches": ["branch2"],
                    "id": "3dfe50e7-9dfb-490c-8c26-858a7c66b797",
                    "summary": {"added": 0, "removed": 0, "updated": 1},
                    "action": "updated",
                    "value": {
                        "path": f"data/{r1}/description/value",
                        "changes": [
                            {
                                "branch": "branch2",
                                "type": "HAS_VALUE",
                                "changed_at": "2023-08-01T11:07:25.255688Z",
                                "action": "updated",
                                "value": {"new": "Second update in Branch", "previous": NULL_VALUE},
                            }
                        ],
                    },
                    "properties": {},
                },
            }
        },
        "summary": {"added": 0, "removed": 0, "updated": 1},
        "action": {"branch2": "updated"},
        "display_label": {"branch2": "repo01"},
    }
    return expected_response


async def test_diff_artifact(db: InfrahubDatabase, client, client_headers, car_person_data_artifact_diff):
    with client:
        response = client.get(
            "/api/diff/artifacts?branch=branch3",
            headers=client_headers,
        )

    assert response.status_code == 200
    data = response.json()

    expected_response = {
        car_person_data_artifact_diff["art2"]: {
            "action": "added",
            "branch": "branch3",
            "display_label": "bolt #444444 - myyartifact",
            "id": car_person_data_artifact_diff["art2"],
            "target": {
                "id": car_person_data_artifact_diff["c2"],
                "kind": "TestElectricCar",
                "display_label": "bolt #444444",
            },
            "item_new": {
                "checksum": "zxcv9063c26263353de24e1b913e1e1c",
                "storage_id": "qwertyui-073f-4173-aa4b-f50e1309f03c",
            },
            "item_previous": None,
        },
        car_person_data_artifact_diff["art1"]: {
            "action": "updated",
            "branch": "branch3",
            "display_label": "volt #444444 - myyartifact",
            "id": car_person_data_artifact_diff["art1"],
            "target": {
                "id": car_person_data_artifact_diff["c1"],
                "kind": "TestElectricCar",
                "display_label": "volt #444444",
            },
            "item_new": {
                "checksum": "zxcv9063c26263353de24e1b911z1x2c3v",
                "storage_id": "azertyui-073f-4173-aa4b-f50e1309f03c",
            },
            "item_previous": {
                "checksum": "60d39063c26263353de24e1b913e1e1c",
                "storage_id": "8caf6f89-073f-4173-aa4b-f50e1309f03c",
            },
        },
        car_person_data_artifact_diff["art3"]: {
            "action": "updated",
            "branch": "branch3",
            "display_label": "nolt #444444 - myyartifact",
            "id": car_person_data_artifact_diff["art3"],
            "target": {
                "id": car_person_data_artifact_diff["c3"],
                "kind": "TestGazCar",
                "display_label": "nolt #444444",
            },
            "item_new": {
                "checksum": "nhytgbvfredc9063c26263353de24e1b913e1e1c",
                "storage_id": "lkjhgfds-073f-4173-aa4b-f50e1309f03c",
            },
            "item_previous": {
                "checksum": "poiuytrewq9063c26263353de24e1b913e1e1c",
                "storage_id": "mnbvcxza-073f-4173-aa4b-f50e1309f03c",
            },
        },
    }

    assert DeepDiff(expected_response, data, ignore_order=True).to_dict() == {}
