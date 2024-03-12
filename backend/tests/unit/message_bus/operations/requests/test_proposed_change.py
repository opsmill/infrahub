import os
from pathlib import Path

import pytest
import ujson
from infrahub_sdk import Config, InfrahubClient
from pytest_httpx import HTTPXMock

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction, InfrahubKind, SchemaPathType
from infrahub.core.diff.model import DiffElementType
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.message_bus.messages import RequestProposedChangeSchemaIntegrity
from infrahub.message_bus.operations.requests import proposed_change
from infrahub.message_bus.types import ProposedChangeBranchDiff
from infrahub.services import InfrahubServices


@pytest.fixture
def service_all(db: InfrahubDatabase, helper):
    config = Config(address="http://mock")
    client = InfrahubClient(config=config, insert_tracker=True)
    bus_simulator = helper.get_message_bus_simulator()
    service = InfrahubServices(message_bus=bus_simulator, client=client, database=db)
    bus_simulator.service = service

    return service


SOURCE_BRANCH_A = "branch2"
DST_BRANCH_A = "main"


@pytest.fixture
async def mock_schema_query_02(helper, httpx_mock: HTTPXMock) -> HTTPXMock:
    response_text = Path(os.path.join(helper.get_fixtures_dir(), "schemas", "schema_02.json")).read_text(
        encoding="UTF-8"
    )

    httpx_mock.add_response(method="GET", url="http://mock/api/schema/?branch=main", json=ujson.loads(response_text))
    return httpx_mock


@pytest.fixture
def branch_diff_01() -> ProposedChangeBranchDiff:
    diff = ProposedChangeBranchDiff(
        diff_summary=[
            {
                "branch": "branch2",
                "action": "updated",
                "kind": "TestPerson",
                "id": "11111111-1111-1111-1111-111111111111",
                "display_label": "",
                "elements": [
                    {
                        "name": "name",
                        "element_type": DiffElementType.ATTRIBUTE.value,
                        "action": DiffAction.UPDATED.value,
                        "summary": {"added": 0, "updated": 1, "removed": 0},
                    }
                ],
            },
            {
                "branch": "main",
                "action": "updated",
                "kind": "TestPerson",
                "id": "22222222-2222-2222-2222-222222222222",
                "display_label": "",
                "elements": [
                    {
                        "name": "height",
                        "element_type": DiffElementType.ATTRIBUTE.value,
                        "action": DiffAction.UPDATED.value,
                        "summary": {"added": 0, "updated": 1, "removed": 0},
                    },
                    {
                        "name": "cars",
                        "element_type": DiffElementType.RELATIONSHIP_MANY.value,
                        "action": DiffAction.UPDATED.value,
                        "summary": {"added": 0, "updated": 1, "removed": 0},
                        "peers": [
                            {"action": DiffAction.REMOVED.value, "summary": {"added": 0, "updated": 0, "removed": 1}},
                            {"action": DiffAction.ADDED.value, "summary": {"added": 1, "updated": 0, "removed": 0}},
                        ],
                    },
                ],
            },
        ],
        repositories=[],
        subscribers=[],
    )

    return diff


@pytest.fixture
async def branch2(db: InfrahubDatabase):
    return await create_branch(branch_name=SOURCE_BRANCH_A, db=db)


@pytest.fixture
async def schema_integrity_01(
    db: InfrahubDatabase, default_branch, register_core_models_schema, branch_diff_01: ProposedChangeBranchDiff
):
    obj = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE, branch=default_branch)
    await obj.new(db=db, name="pc1", source_branch=SOURCE_BRANCH_A, destination_branch="main")
    await obj.save(db=db)

    message = RequestProposedChangeSchemaIntegrity(
        proposed_change=obj.id,
        source_branch=SOURCE_BRANCH_A,
        source_branch_sync_with_git=False,
        destination_branch="main",
        branch_diff=branch_diff_01,
    )
    return message


async def test_get_proposed_change_schema_integrity_constraints(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema, schema_integrity_01
):
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    constraints = await proposed_change._get_proposed_change_schema_integrity_constraints(
        message=schema_integrity_01, schema=schema
    )
    assert len(constraints) == 13
    dumped_constraints = [c.model_dump() for c in constraints]
    assert {
        "constraint_name": "relationship.optional.update",
        "path": {
            "field_name": "cars",
            "path_type": SchemaPathType.RELATIONSHIP,
            "property_name": "optional",
            "schema_id": None,
            "schema_kind": "TestPerson",
        },
    } in dumped_constraints
    assert {
        "constraint_name": "relationship.peer.update",
        "path": {
            "field_name": "cars",
            "path_type": SchemaPathType.RELATIONSHIP,
            "property_name": "peer",
            "schema_id": None,
            "schema_kind": "TestPerson",
        },
    } in dumped_constraints
    assert {
        "constraint_name": "relationship.cardinality.update",
        "path": {
            "field_name": "cars",
            "path_type": SchemaPathType.RELATIONSHIP,
            "property_name": "cardinality",
            "schema_id": None,
            "schema_kind": "TestPerson",
        },
    } in dumped_constraints
    assert {
        "constraint_name": "relationship.min_count.update",
        "path": {
            "field_name": "cars",
            "path_type": SchemaPathType.RELATIONSHIP,
            "property_name": "min_count",
            "schema_id": None,
            "schema_kind": "TestPerson",
        },
    } in dumped_constraints
    assert {
        "constraint_name": "relationship.max_count.update",
        "path": {
            "field_name": "cars",
            "path_type": SchemaPathType.RELATIONSHIP,
            "property_name": "max_count",
            "schema_id": None,
            "schema_kind": "TestPerson",
        },
    } in dumped_constraints
    assert {
        "constraint_name": "attribute.optional.update",
        "path": {
            "field_name": "height",
            "path_type": SchemaPathType.ATTRIBUTE,
            "property_name": "optional",
            "schema_id": None,
            "schema_kind": "TestPerson",
        },
    } in dumped_constraints
    assert {
        "constraint_name": "attribute.unique.update",
        "path": {
            "field_name": "height",
            "path_type": SchemaPathType.ATTRIBUTE,
            "property_name": "unique",
            "schema_id": None,
            "schema_kind": "TestPerson",
        },
    } in dumped_constraints
    assert {
        "constraint_name": "attribute.optional.update",
        "path": {
            "field_name": "name",
            "path_type": SchemaPathType.ATTRIBUTE,
            "property_name": "optional",
            "schema_id": None,
            "schema_kind": "TestPerson",
        },
    } in dumped_constraints
    assert {
        "constraint_name": "attribute.unique.update",
        "path": {
            "field_name": "name",
            "path_type": SchemaPathType.ATTRIBUTE,
            "property_name": "unique",
            "schema_id": None,
            "schema_kind": "TestPerson",
        },
    } in dumped_constraints
    assert {
        "constraint_name": "node.parent.update",
        "path": {
            "field_name": "parent",
            "path_type": SchemaPathType.NODE,
            "property_name": "parent",
            "schema_id": None,
            "schema_kind": "CoreStandardGroup",
        },
    } in dumped_constraints
    assert {
        "constraint_name": "node.children.update",
        "path": {
            "field_name": "children",
            "path_type": SchemaPathType.NODE,
            "property_name": "children",
            "schema_id": None,
            "schema_kind": "CoreStandardGroup",
        },
    } in dumped_constraints
    assert {
        "constraint_name": "node.parent.update",
        "path": {
            "field_name": "parent",
            "path_type": SchemaPathType.NODE,
            "property_name": "parent",
            "schema_id": None,
            "schema_kind": "CoreGraphQLQueryGroup",
        },
    } in dumped_constraints
    assert {
        "constraint_name": "node.children.update",
        "path": {
            "field_name": "children",
            "path_type": SchemaPathType.NODE,
            "property_name": "children",
            "schema_id": None,
            "schema_kind": "CoreGraphQLQueryGroup",
        },
    } in dumped_constraints


async def test_schema_integrity(
    db: InfrahubDatabase,
    default_branch,
    register_core_models_schema,
    car_person_schema,
    schema_integrity_01,
    service_all,
    car_accord_main: Node,
    car_volt_main: Node,
    person_john_main,
    httpx_mock: HTTPXMock,
):
    branch2 = await create_branch(branch_name=SOURCE_BRANCH_A, db=db)

    person = await Node.init(db=db, schema="TestPerson", branch=branch2)
    await person.new(db=db, name="ALFRED", height=160, cars=[car_accord_main.id])
    await person.save(db=db)

    branch2_schema = registry.schema.get_schema_branch(name=branch2.name)
    person_schema = branch2_schema.get(name="TestPerson")
    name_attr = person_schema.get_attribute(name="name")
    name_attr.regex = r"^[A-Z]+$"
    branch2_schema.set(name="TestPerson", schema=person_schema)

    # Ignore creation of Task Report response
    httpx_mock.add_response(method="POST", url="http://mock/graphql", json={"data": {}})
    await proposed_change.schema_integrity(message=schema_integrity_01, service=service_all)

    checks = await registry.manager.query(db=db, schema=InfrahubKind.SCHEMACHECK)
    assert len(checks) == 1
    check = checks[0]
    assert check.conclusion.value == "failure"
    assert check.conflicts.value == [
        {
            "branch": "placeholder",
            "id": person_john_main.id,
            "kind": "TestPerson",
            "name": "schema/TestPerson/name/regex",
            "path": "schema/TestPerson/name/regex",
            "type": "attribute.regex.update",
            "value": "NA",
        }
    ]
