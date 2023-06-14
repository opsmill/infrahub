from fastapi.testclient import TestClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.utils import count_relationships


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
    assert len(schema["nodes"]) == 18
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
    assert len(schema["nodes"]) == 18


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
    admin_headers,
    default_branch: Branch,
    authentication_base,
    helper,
):
    # Must execute in a with block to execute the startup/shutdown events

    with client:
        creation = client.post("/schema/load", headers=admin_headers, json=helper.schema_file("infra_simple_01.json"))
        read = client.get("/schema", headers=admin_headers)

    assert creation.status_code == 202
    assert read.status_code == 200
    nodes = read.json()["nodes"]
    device = [node for node in nodes if node["name"] == "device"]
    assert device
    device = device[0]
    attributes = {attrib["name"]: attrib["order_weight"] for attrib in device["attributes"]}
    relationships = {attrib["name"]: attrib["order_weight"] for attrib in device["relationships"]}
    assert attributes["name"] == 1000
    assert attributes["description"] == 900
    assert attributes["type"] == 3000
    assert relationships["interfaces"] == 450
    assert relationships["tags"] == 101000


async def test_schema_load_endpoint_idempotent_simple(
    session,
    client: TestClient,
    admin_headers,
    default_branch: Branch,
    register_core_schema_db,
    authentication_base,
    helper,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        creation = client.post("/schema/load", headers=admin_headers, json=helper.schema_file("infra_simple_01.json"))
        read = client.get("/schema", headers=admin_headers)

        nbr_rels = await count_relationships(session=session)

        assert creation.status_code == 202
        assert read.status_code == 200
        nodes = read.json()["nodes"]
        device = [node for node in nodes if node["name"] == "device"]
        assert device
        device = device[0]
        attributes = {attrib["name"]: attrib["order_weight"] for attrib in device["attributes"]}
        relationships = {attrib["name"]: attrib["order_weight"] for attrib in device["relationships"]}
        assert attributes["name"] == 1000
        assert attributes["description"] == 900
        assert attributes["type"] == 3000
        assert relationships["interfaces"] == 450
        assert relationships["tags"] == 101000

        creation = client.post("/schema/load", headers=admin_headers, json=helper.schema_file("infra_simple_01.json"))
        read = client.get("/schema", headers=admin_headers)

        assert creation.status_code == 202
        assert read.status_code == 200

        assert nbr_rels == await count_relationships(session=session)


async def test_schema_load_endpoint_valid_with_generics(
    session,
    client: TestClient,
    admin_headers,
    default_branch: Branch,
    authentication_base,
    helper,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response1 = client.post(
            "/schema/load", headers=admin_headers, json=helper.schema_file("infra_w_generics_01.json")
        )
        assert response1.status_code == 202

        response2 = client.get("/schema", headers=admin_headers)
        assert response2.status_code == 200

    schema = response2.json()
    assert len(schema["generics"]) == 3


async def test_schema_load_endpoint_idempotent_with_generics(
    session,
    client: TestClient,
    admin_headers,
    default_branch: Branch,
    authentication_base,
    helper,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response1 = client.post(
            "/schema/load", headers=admin_headers, json=helper.schema_file("infra_w_generics_01.json")
        )
        assert response1.status_code == 202

        response2 = client.get("/schema", headers=admin_headers)
        assert response2.status_code == 200

        schema = response2.json()
        assert len(schema["generics"]) == 3

        nbr_rels = await count_relationships(session=session)

        response3 = client.post(
            "/schema/load", headers=admin_headers, json=helper.schema_file("infra_w_generics_01.json")
        )
        assert response3.status_code == 202

        response4 = client.get("/schema", headers=admin_headers)
        assert response4.status_code == 200

        assert nbr_rels == await count_relationships(session=session)


async def test_schema_load_endpoint_valid_with_extensions(
    session,
    client: TestClient,
    admin_headers,
    default_branch: Branch,
    authentication_base,
    helper,
):
    org_schema = registry.schema.get(name="Organization", branch=default_branch.name)
    initial_nbr_relationships = len(org_schema.relationships)

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post(
            "/schema/load", headers=admin_headers, json=helper.schema_file("infra_w_extensions_01.json")
        )

    assert response.status_code == 202

    org_schema = registry.schema.get(name="Organization", branch=default_branch.name)
    assert len(org_schema.relationships) == initial_nbr_relationships + 1


async def test_schema_load_endpoint_not_valid_simple_02(
    session,
    client: TestClient,
    admin_headers,
    default_branch: Branch,
    authentication_base,
    helper,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post(
            "/schema/load", headers=admin_headers, json=helper.schema_file("not_valid_simple_02.json")
        )

    assert response.status_code == 422


async def test_schema_load_endpoint_not_valid_simple_03(
    session,
    client: TestClient,
    admin_headers,
    default_branch: Branch,
    authentication_base,
    helper,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post(
            "/schema/load", headers=admin_headers, json=helper.schema_file("not_valid_simple_03.json")
        )

    assert response.status_code == 422


async def test_schema_load_endpoint_not_valid_simple_04(
    session,
    client: TestClient,
    admin_headers,
    default_branch: Branch,
    authentication_base,
    helper,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post(
            "/schema/load", headers=admin_headers, json=helper.schema_file("not_valid_simple_04.json")
        )

    assert response.status_code == 422


async def test_schema_load_endpoint_not_valid_simple_05(
    session,
    client: TestClient,
    admin_headers,
    default_branch: Branch,
    authentication_base,
    helper,
):
    with client:
        response = client.post(
            "/schema/load", headers=admin_headers, json=helper.schema_file("not_valid_simple_05.json")
        )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Name can not be set to a reserved keyword 'class' is not allowed."


async def test_schema_load_endpoint_not_valid_with_generics_02(
    session,
    client: TestClient,
    admin_headers,
    default_branch: Branch,
    authentication_base,
    helper,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post(
            "/schema/load", headers=admin_headers, json=helper.schema_file("not_valid_w_generics_02.json")
        )

    assert response.status_code == 422
