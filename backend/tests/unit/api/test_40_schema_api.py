from fastapi.testclient import TestClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch


async def test_schema_read_endpoint_default_branch(
    session, client, client_headers, default_branch: Branch, car_person_data_generic
):
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
    assert len(schema["nodes"]) == 17
    assert len(schema["generics"]) == 3
    assert schema["generics"][0]["used_by"]


async def test_schema_read_endpoint_branch1(
    session, client: TestClient, client_headers, default_branch: Branch, car_person_data_generic
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
    assert len(schema["nodes"]) == 17


async def test_schema_read_endpoint_wrong_branch(
    session, client: TestClient, client_headers, default_branch: Branch, car_person_data_generic
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
    default_branch: Branch,
    register_core_models_schema,
    schema_file_infra_simple_01,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        creation = client.post("/schema/load", headers=client_headers, json=schema_file_infra_simple_01)
        read = client.get("/schema", headers=client_headers)

    assert creation.status_code == 202
    assert read.status_code == 200
    nodes = read.json()["nodes"]
    device = [node for node in nodes if node["name"] == "device"]
    assert device
    device = device[0]
    attributes = {attrib["name"]: attrib["order_weight"] for attrib in device["attributes"]}
    assert attributes["name"] == 1000
    assert attributes["description"] == 900
    assert attributes["type"] == 3000


async def test_schema_load_endpoint_valid_with_generics(
    session,
    client: TestClient,
    client_headers,
    default_branch: Branch,
    register_core_models_schema,
    schema_file_infra_w_generics_01,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response1 = client.post("/schema/load", headers=client_headers, json=schema_file_infra_w_generics_01)
        assert response1.status_code == 202

        response2 = client.get("/schema", headers=client_headers)
        assert response2.status_code == 200

    schema = response2.json()
    assert len(schema["generics"]) == 3


async def test_schema_load_endpoint_valid_with_extensions(
    session,
    client: TestClient,
    client_headers,
    default_branch: Branch,
    register_core_models_schema,
    schema_file_infra_w_extensions_01,
):
    org_schema = registry.schema.get(name="Organization", branch=default_branch.name)
    initial_nbr_relationships = len(org_schema.relationships)

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post("/schema/load", headers=client_headers, json=schema_file_infra_w_extensions_01)

    assert response.status_code == 202

    org_schema = registry.schema.get(name="Organization")
    assert len(org_schema.relationships) == initial_nbr_relationships + 1


async def test_schema_load_endpoint_not_valid_simple_02(
    session,
    client: TestClient,
    client_headers,
    default_branch: Branch,
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
    default_branch: Branch,
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
    default_branch: Branch,
    register_core_models_schema,
    schema_file_not_valid_simple_04,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post("/schema/load", headers=client_headers, json=schema_file_not_valid_simple_04)

    assert response.status_code == 422


async def test_schema_load_endpoint_not_valid_simple_05(
    session,
    client: TestClient,
    client_headers,
    default_branch: Branch,
    register_core_models_schema,
    schema_file_not_valid_simple_05,
):
    with client:
        response = client.post("/schema/load", headers=client_headers, json=schema_file_not_valid_simple_05)

    assert response.status_code == 422
    response.json()["detail"][0]["msg"] == "Name can not be set to a reserved keyword 'class' is not allowed."


async def test_schema_load_endpoint_not_valid_with_generics_02(
    session,
    client: TestClient,
    client_headers,
    default_branch: Branch,
    register_core_models_schema,
    schema_file_not_valid_w_generics_02,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post("/schema/load", headers=client_headers, json=schema_file_not_valid_w_generics_02)

    assert response.status_code == 422
