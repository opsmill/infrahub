from fastapi.testclient import TestClient

from infrahub.core.initialization import create_branch


async def test_schema_read_endpoint_default_branch(
    session, client: TestClient, client_headers, default_branch, car_person_data
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
    assert len(schema["nodes"]) == 21


async def test_schema_read_endpoint_branch1(
    session, client: TestClient, client_headers, default_branch, car_person_data
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
    assert len(schema["nodes"]) == 21


async def test_schema_read_endpoint_wrong_branch(
    session, client: TestClient, client_headers, default_branch, car_person_data
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
