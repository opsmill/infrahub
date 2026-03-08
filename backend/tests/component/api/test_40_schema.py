import pytest
from fastapi.testclient import TestClient

from infrahub import config
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import RESERVED_ATTR_REL_HIERARCHICAL_NAMES, InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot, core_models
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from tests.conftest import BusRPCMock, TestHelper


async def test_schema_read_endpoint_default_branch(
    db: InfrahubDatabase,
    client: TestClient,
    client_headers: dict[str, str],
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    car_person_data_generic: dict[str, Node],
) -> None:
    with client:
        response = client.get(
            "/api/schema",
            headers=client_headers,
        )

    assert response.status_code == 200
    assert response.json() is not None

    schema = response.json()
    core_nodes = [node for node in core_models["nodes"] if node["namespace"] != "Internal"]
    core_generics = [node for node in core_models["generics"] if node["namespace"] != "Internal"]

    expected_nodes = {dict(item).get("name") for item in core_nodes + car_person_schema_generics.nodes}
    expected_generics = {dict(item).get("name") for item in core_generics + car_person_schema_generics.generics}

    assert "nodes" in schema
    assert "generics" in schema
    assert len(schema["nodes"]) == len(expected_nodes)
    assert len(schema["generics"]) == len(expected_generics)

    generics = {item["kind"]: item for item in schema["generics"]}
    assert generics["TestCar"]["used_by"]


async def test_schema_read_endpoint_branch1(
    db: InfrahubDatabase,
    client: TestClient,
    client_headers: dict[str, str],
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    car_person_data_generic: dict[str, Node],
) -> None:
    await create_branch(branch_name="branch1", db=db)

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get(
            "/api/schema?branch=branch1",
            headers=client_headers,
        )

    assert response.status_code == 200
    assert response.json() is not None

    schema = response.json()

    core_nodes = [node for node in core_models["nodes"] if node["namespace"] != "Internal"]

    expected_nodes = {dict(node).get("name") for node in core_nodes + car_person_schema_generics.nodes}
    assert "nodes" in schema
    assert len(schema["nodes"]) == len(expected_nodes)


async def test_schema_read_endpoint_wrong_branch(
    db: InfrahubDatabase,
    client: TestClient,
    client_headers: dict[str, str],
    default_branch: Branch,
    car_person_data_generic: dict[str, Node],
) -> None:
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get(
            "/api/schema?branch=notvalid",
            headers=client_headers,
        )

    assert response.status_code == 400
    assert response.json() is not None


async def test_schema_load_blocked_on_merged_branch(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    prefect_test_fixture: None,
    workflow_local: WorkflowLocalExecution,
    authentication_base: Node,
    helper: TestHelper,
) -> None:
    """Test that schema load returns 422 on merged branches."""
    branch = await create_branch(branch_name="merged-schema-test", db=db)
    branch.status = BranchStatus.MERGED
    await branch.save(db=db)
    registry.branch[branch.name] = branch

    with client:
        response = client.post(
            f"/api/schema/load?branch={branch.name}",
            headers=admin_headers,
            json={"schemas": [helper.schema_file("infra_simple_01.json")]},
        )

    assert response.status_code == 422
    assert "has been merged and is read-only" in response.json()["errors"][0]["message"]


async def test_schema_load_blocked_on_need_rebase_branch(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    prefect_test_fixture: None,
    workflow_local: WorkflowLocalExecution,
    authentication_base: Node,
    helper: TestHelper,
) -> None:
    """Test that schema load returns 422 on branches needing rebase."""
    branch = await create_branch(branch_name="rebase-schema-test", db=db)
    branch.status = BranchStatus.NEED_REBASE
    await branch.save(db=db)
    registry.branch[branch.name] = branch

    with client:
        response = client.post(
            f"/api/schema/load?branch={branch.name}",
            headers=admin_headers,
            json={"schemas": [helper.schema_file("infra_simple_01.json")]},
        )

    assert response.status_code == 422
    assert "must be rebased" in response.json()["errors"][0]["message"]


async def test_schema_summary_default_branch(
    db: InfrahubDatabase,
    client: TestClient,
    client_headers: dict[str, str],
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    car_person_data_generic: dict[str, Node],
) -> None:
    with client:
        response = client.get(
            "/api/schema/summary",
            headers=client_headers,
        )

    assert response.status_code == 200
    assert response.json() is not None

    schema = response.json()

    assert "nodes" in schema
    assert "generics" in schema
    assert isinstance(schema["nodes"][InfrahubKind.TAG], str)


async def test_schema_kind_default_branch(
    db: InfrahubDatabase,
    client: TestClient,
    client_headers: dict[str, str],
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    car_person_data_generic: dict[str, Node],
) -> None:
    with client:
        response = client.get(
            f"/api/schema/{InfrahubKind.TAG}",
            headers=client_headers,
        )

    assert response.status_code == 200
    assert response.json() is not None

    schema = response.json()

    assert "id" in schema
    assert "hash" in schema
    assert "relationships" in schema


async def test_json_schema_kind_default_branch(
    db: InfrahubDatabase,
    client: TestClient,
    client_headers: dict[str, str],
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    car_person_data_generic: dict[str, Node],
) -> None:
    with client:
        response = client.get(
            f"/api/schema/json_schema/{InfrahubKind.IPPREFIX}",
            headers=client_headers,
        )

    assert response.status_code == 200
    assert response.json() is not None

    schema = response.json()

    assert "$schema" in schema
    assert "title" in schema
    assert "type" in schema
    assert "properties" in schema
    assert "required" in schema
    assert "description" in schema
    assert "prefix" in schema["properties"]["member_type"]["enum"]


async def test_schema_kind_not_valid(
    db: InfrahubDatabase,
    client: TestClient,
    client_headers: dict[str, str],
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    car_person_data_generic: dict[str, Node],
) -> None:
    with client:
        response = client.get(
            "/api/schema/NotPresent",
            headers=client_headers,
        )

    assert response.status_code == 422
    assert response.json()["errors"][0]["message"] == "Unable to find the schema 'NotPresent' in the registry"


async def test_schema_load_permission_failure(
    db: InfrahubDatabase,
    client: TestClient,
    first_account: Node,
    default_branch: Branch,
    prefect_test_fixture: None,
    workflow_local: WorkflowLocalExecution,
    authentication_base: Node,
    helper: TestHelper,
) -> None:
    token = await Node.init(db=db, schema=InfrahubKind.ACCOUNTTOKEN)
    await token.new(db=db, token="unprivileged", account=first_account)
    await token.save(db=db)

    # Load the schema in the database
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    await registry.schema.load_schema_to_db(schema=schema, branch=default_branch, db=db)

    # Must execute in a with block to execute the startup/shutdown event
    with client:
        response = client.post(
            "/api/schema/load",
            headers={"X-INFRAHUB-KEY": "unprivileged"},
            json={"schemas": [helper.schema_file("infra_simple_01.json")]},
        )

    assert response.status_code == 403
    assert response.json()["errors"][0]["message"] == "You are not allowed to manage the schema"


async def test_schema_load_restricted_namespace(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    prefect_test_fixture: None,
    workflow_local: WorkflowLocalExecution,
    authentication_base: Node,
    helper: TestHelper,
) -> None:
    with client:
        response = client.post(
            "/api/schema/load",
            headers=admin_headers,
            json={"schemas": [helper.schema_file("restricted_namespace_01.json")]},
        )

    assert response.status_code == 422
    assert response.json()["errors"][0]["message"] == "Restricted namespace 'Internal' used on 'Timestamp'"


async def test_schema_load_endpoint_not_valid_simple_02(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    prefect_test_fixture: None,
    workflow_local: WorkflowLocalExecution,
    authentication_base: Node,
    helper: TestHelper,
) -> None:
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post(
            "/api/schema/load",
            headers=admin_headers,
            json={"schemas": [helper.schema_file("not_valid_simple_02.json")]},
        )

    assert response.status_code == 422


async def test_schema_load_endpoint_not_valid_simple_03(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    prefect_test_fixture: None,
    workflow_local: WorkflowLocalExecution,
    authentication_base: Node,
    helper: TestHelper,
) -> None:
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post(
            "/api/schema/load",
            headers=admin_headers,
            json={"schemas": [helper.schema_file("not_valid_simple_03.json")]},
        )

    assert response.status_code == 422


async def test_schema_load_endpoint_not_valid_simple_04(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    prefect_test_fixture: None,
    workflow_local: WorkflowLocalExecution,
    authentication_base: Node,
    helper: TestHelper,
) -> None:
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post(
            "/api/schema/load",
            headers=admin_headers,
            json={"schemas": [helper.schema_file("not_valid_simple_04.json")]},
        )

    assert response.status_code == 422


async def test_schema_load_endpoint_not_valid_simple_05(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    prefect_test_fixture: None,
    workflow_local: WorkflowLocalExecution,
    authentication_base: Node,
    helper: TestHelper,
) -> None:
    with client:
        response = client.post(
            "/api/schema/load",
            headers=admin_headers,
            json={"schemas": [helper.schema_file("not_valid_simple_05.json")]},
        )

    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "Value error, Name can not be set to a reserved keyword 'None' is not allowed."
    )


async def test_schema_load_endpoint_not_valid_with_generics_02(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    authentication_base: Node,
    helper: TestHelper,
) -> None:
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post(
            "/api/schema/load",
            headers=admin_headers,
            json={"schemas": [helper.schema_file("not_valid_w_generics_02.json")]},
        )

    assert response.status_code == 422


async def test_schema_load_endpoint_python_keyword_attribute(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    authentication_base: Node,
    helper: TestHelper,
) -> None:
    """Test that loading a schema with Python keyword as attribute name fails with proper error."""
    with client:
        response = client.post(
            "/api/schema/load",
            headers=admin_headers,
            json={"schemas": [helper.schema_file("python_keyword_from.json")]},
        )

    assert response.status_code == 422
    assert (
        "Python keyword 'from' cannot be used as an attribute name on 'InfraRoutingPolicy'"
        in response.json()["errors"][0]["message"]
    )


async def test_schema_load_endpoint_constraints_not_valid(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    rpc_bus: BusRPCMock,
    default_branch: Branch,
    prefect_test_fixture: None,
    workflow_local: WorkflowLocalExecution,
    authentication_base: Node,
    car_person_schema: SchemaBranch,
    car_accord_main: Node,
    car_volt_main: Node,
    person_john_main: Node,
    helper: TestHelper,
) -> None:
    # Load the schema in the database
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    await registry.schema.load_schema_to_db(schema=schema, branch=default_branch, db=db)

    person_schema = {
        "name": "Person",
        "namespace": "Test",
        "default_filter": "name__value",
        "display_labels": ["name__value"],
        "branch": "aware",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True, "regex": "^[A-Z]+$"},
            {"name": "height", "kind": "Number", "optional": True},
        ],
        "relationships": [{"name": "cars", "peer": "TestCar", "cardinality": "many", "direction": "inbound"}],
    }

    # Must execute in a with block to execute the startup/shutdown events
    # async with AsyncClient(app=app, base_url="http://test") as ac:
    with client:
        response = client.post(
            "/api/schema/load",
            headers=admin_headers,
            json={"schemas": [{"version": "1.0", "nodes": [person_schema]}]},
        )

    error_message = (
        "Attribute-level 'regex' constraint violation on schema 'TestPerson'."
        f" Node (John) is not compliant."
        f" The error relates to field name='{person_john_main.name.value}'."
    )
    assert response.json() == {
        "data": None,
        "errors": [{"extensions": {"code": 422}, "message": error_message}],
    }
    assert response.status_code == 422


@pytest.mark.parametrize("allow_anonymous_access", [False, True])
async def test_schema_read_endpoints_anonymous_account(
    db: InfrahubDatabase,
    client: TestClient,
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    allow_anonymous_access: bool,
) -> None:
    config.SETTINGS.main.allow_anonymous_access = allow_anonymous_access

    with client:
        response = client.get("/api/schema")

    assert response.status_code == 200 if allow_anonymous_access else 401

    with client:
        response = client.get("/api/schema/TestCar")

    assert response.status_code == 200 if allow_anonymous_access else 401

    with client:
        response = client.get("/api/schema/summary")

    assert response.status_code == 200 if allow_anonymous_access else 401

    with client:
        response = client.get("/api/schema/json_schema/TestCar")

    assert response.status_code == 200 if allow_anonymous_access else 401


@pytest.mark.parametrize(
    "reserved_name",
    [pytest.param(reserved_name, id=reserved_name) for reserved_name in RESERVED_ATTR_REL_HIERARCHICAL_NAMES],
)
async def test_schema_load_restricted_names(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    prefect_test_fixture: None,
    workflow_local: WorkflowLocalExecution,
    authentication_base: Node,
    helper: TestHelper,
    reserved_name: str,
) -> None:
    schema = helper.schema_file("restricted_names_01.json")
    schema["nodes"][1]["relationships"][0]["name"] = reserved_name
    with client:
        response = client.post(
            "/api/schema/load",
            headers=admin_headers,
            json={"schemas": [schema]},
        )

    assert response.status_code == 422
    assert (
        response.json()["errors"][0]["message"]
        == f"TestingParent: {reserved_name} isn't allowed as a relationship name on hierarchical nodes."
    )

    schema = helper.schema_file("restricted_names_02.json")
    schema["nodes"][1]["attributes"][0]["name"] = reserved_name
    with client:
        response = client.post(
            "/api/schema/load",
            headers=admin_headers,
            json={"schemas": [schema]},
        )

    assert response.status_code == 422
    assert (
        response.json()["errors"][0]["message"]
        == f"TestingParent: {reserved_name} isn't allowed as an attribute name on hierarchical nodes."
    )
