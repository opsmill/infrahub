from fastapi.testclient import TestClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot, core_models
from infrahub.database import InfrahubDatabase


async def test_schema_read_endpoint_default_branch(
    db: InfrahubDatabase,
    client: TestClient,
    client_headers,
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    car_person_data_generic,
):
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

    expected_nodes = set([dict(item).get("name") for item in core_nodes + car_person_schema_generics.nodes])
    expected_generics = set([dict(item).get("name") for item in core_generics + car_person_schema_generics.generics])

    assert "nodes" in schema
    assert "generics" in schema
    assert len(schema["nodes"]) == len(expected_nodes)
    assert len(schema["generics"]) == len(expected_generics)

    generics = {item["kind"]: item for item in schema["generics"]}
    assert generics["TestCar"]["used_by"]


async def test_schema_read_endpoint_branch1(
    db: InfrahubDatabase,
    client: TestClient,
    client_headers,
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    car_person_data_generic,
):
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

    expected_nodes = set([dict(node).get("name") for node in core_nodes + car_person_schema_generics.nodes])
    assert "nodes" in schema
    assert len(schema["nodes"]) == len(expected_nodes)


async def test_schema_read_endpoint_wrong_branch(
    db: InfrahubDatabase, client: TestClient, client_headers, default_branch: Branch, car_person_data_generic
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get(
            "/api/schema?branch=notvalid",
            headers=client_headers,
        )

    assert response.status_code == 400
    assert response.json() is not None


async def test_schema_summary_default_branch(
    db: InfrahubDatabase,
    client: TestClient,
    client_headers,
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    car_person_data_generic,
):
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
    client_headers,
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    car_person_data_generic,
):
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
    client,
    client_headers,
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    car_person_data_generic,
):
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
    client_headers,
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    car_person_data_generic,
):
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
    first_account,
    default_branch: Branch,
    prefect_test_fixture,
    workflow_local,
    authentication_base,
    helper,
):
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
    admin_headers,
    default_branch: Branch,
    prefect_test_fixture,
    workflow_local,
    authentication_base,
    helper,
):
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
    admin_headers,
    default_branch: Branch,
    prefect_test_fixture,
    workflow_local,
    authentication_base,
    helper,
):
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
    admin_headers,
    default_branch: Branch,
    prefect_test_fixture,
    workflow_local,
    authentication_base,
    helper,
):
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
    admin_headers,
    default_branch: Branch,
    prefect_test_fixture,
    workflow_local,
    authentication_base,
    helper,
):
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
    admin_headers,
    default_branch: Branch,
    prefect_test_fixture,
    workflow_local,
    authentication_base,
    helper,
):
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
    admin_headers,
    default_branch: Branch,
    authentication_base,
    helper,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post(
            "/api/schema/load",
            headers=admin_headers,
            json={"schemas": [helper.schema_file("not_valid_w_generics_02.json")]},
        )

    assert response.status_code == 422


async def test_schema_load_endpoint_constraints_not_valid(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers,
    rpc_bus,
    default_branch: Branch,
    prefect_test_fixture,
    workflow_local,
    authentication_base,
    car_person_schema,
    car_accord_main,
    car_volt_main,
    person_john_main,
    helper,
):
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

    error_message = f"Node John (TestPerson: {person_john_main.id}) is not compatible with the constraint 'attribute.regex.update' at 'schema/TestPerson/name/regex'"  # noqa: E501
    assert response.json() == {
        "data": None,
        "errors": [{"extensions": {"code": 422}, "message": error_message}],
    }
    assert response.status_code == 422
