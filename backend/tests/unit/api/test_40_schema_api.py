from fastapi.testclient import TestClient

from infrahub.core import registry
from infrahub.core.initialization import create_branch
from infrahub.core.manager import SchemaManager
from infrahub.core.schema import full_schema_to_schema_root


async def test_schema_read_endpoint_default_branch(
    session, client: TestClient, client_headers, default_branch, car_person_data_generic
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get(
            "/schema",
            headers=client_headers,
        )

    assert response.status_code == 200
    assert response.json() is not None

    schema = response.json()

    assert "nodes" in schema
    assert "generics" in schema
    assert len(schema["nodes"]) == 22
    assert len(schema["generics"]) == 3
    assert schema["generics"][0]["used_by"]


async def test_schema_read_endpoint_branch1(
    session, client: TestClient, client_headers, default_branch, car_person_data_generic
):
    await create_branch(branch_name="branch1", session=session)

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get(
            "/schema?branch=branch1",
            headers=client_headers,
        )

    assert response.status_code == 200
    assert response.json() is not None

    schema = response.json()

    assert "nodes" in schema
    assert len(schema["nodes"]) == 22


async def test_schema_read_endpoint_wrong_branch(
    session, client: TestClient, client_headers, default_branch, car_person_data_generic
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get(
            "/schema?branch=notvalid",
            headers=client_headers,
        )

    assert response.status_code == 400
    assert response.json() is not None


async def test_schema_load_endpoint_valid_simple(
    session,
    client: TestClient,
    client_headers,
    default_branch,
    register_core_models_schema,
    schema_file_infra_simple_01,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post("/schema/load", headers=client_headers, json=schema_file_infra_simple_01)

    assert response.status_code == 202


async def test_schema_load_endpoint_valid_with_generics(
    session,
    client: TestClient,
    client_headers,
    default_branch,
    register_core_models_schema,
    schema_file_infra_w_generics_01,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post("/schema/load", headers=client_headers, json=schema_file_infra_w_generics_01)

    assert response.status_code == 202


async def test_schema_load_endpoint_valid_with_extensions(
    session,
    client: TestClient,
    client_headers,
    default_branch,
    register_core_models_schema,
    schema_file_infra_w_extensions_01,
):
    # Load the schema into the database, by default it's only available in the registry
    full_schema = full_schema_to_schema_root(registry.get_full_schema())
    await SchemaManager.load_schema_to_db(full_schema, session=session)

    org_schema = registry.get_schema(name="Organization")
    initial_nbr_relationships = len(org_schema.relationships)

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post("/schema/load", headers=client_headers, json=schema_file_infra_w_extensions_01)

    assert response.status_code == 202

    # Pull the schema from the db to validate that it has been properly updated
    schema = await SchemaManager.load_schema_from_db(session=session)
    await SchemaManager.register_schema_to_registry(schema=schema)

    org_schema = registry.get_schema(name="Organization")
    assert len(org_schema.relationships) == initial_nbr_relationships + 1


async def test_schema_load_endpoint_not_valid_simple_02(
    session,
    client: TestClient,
    client_headers,
    default_branch,
    register_core_models_schema,
    schema_file_not_valid_simple_02,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post("/schema/load", headers=client_headers, json=schema_file_not_valid_simple_02)

    assert response.status_code == 422


async def test_schema_load_endpoint_not_valid_simple_03(
    session,
    client: TestClient,
    client_headers,
    default_branch,
    register_core_models_schema,
    schema_file_not_valid_simple_03,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post("/schema/load", headers=client_headers, json=schema_file_not_valid_simple_03)

    assert response.status_code == 422


async def test_schema_load_endpoint_not_valid_simple_04(
    session,
    client: TestClient,
    client_headers,
    default_branch,
    register_core_models_schema,
    schema_file_not_valid_simple_04,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post("/schema/load", headers=client_headers, json=schema_file_not_valid_simple_04)

    assert response.status_code == 422


async def test_schema_load_endpoint_not_valid_with_generics_02(
    session,
    client: TestClient,
    client_headers,
    default_branch,
    register_core_models_schema,
    schema_file_not_valid_w_generics_02,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post("/schema/load", headers=client_headers, json=schema_file_not_valid_w_generics_02)

    assert response.status_code == 422
