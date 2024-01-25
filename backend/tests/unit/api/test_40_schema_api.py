from fastapi.testclient import TestClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.schema import SchemaRoot, core_models
from infrahub.core.utils import count_relationships
from infrahub.database import InfrahubDatabase


async def test_schema_read_endpoint_default_branch(
    db: InfrahubDatabase,
    client,
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
    client,
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
    client,
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
    assert "filters" in schema
    assert "relationships" in schema


async def test_schema_kind_not_valid(
    db: InfrahubDatabase,
    client,
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


async def test_schema_load_endpoint_valid_simple(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers,
    default_branch: Branch,
    authentication_base,
    helper,
):
    # Must execute in a with block to execute the startup/shutdown events

    with client:
        creation = client.post(
            "/api/schema/load", headers=admin_headers, json={"schemas": [helper.schema_file("infra_simple_01.json")]}
        )
        read = client.get("/api/schema", headers=admin_headers)

    assert creation.json() == {}
    assert creation.status_code == 202
    assert read.status_code == 200
    nodes = read.json()["nodes"]
    device = [node for node in nodes if node["name"] == "Device"]
    assert device
    device = device[0]
    attributes = {attrib["name"]: attrib["order_weight"] for attrib in device["attributes"]}
    relationships = {attrib["name"]: attrib["order_weight"] for attrib in device["relationships"]}
    assert attributes["name"] == 1000
    assert attributes["description"] == 900
    assert attributes["type"] == 3000
    assert relationships["interfaces"] == 450
    assert relationships["tags"] == 7000


async def test_schema_load_restricted_namespace(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers,
    default_branch: Branch,
    authentication_base,
    helper,
):
    with client:
        response = client.post(
            "/api/schema/load",
            headers=admin_headers,
            json={"schemas": [helper.schema_file("restricted_namespace_01.json")]},
        )

    assert response.status_code == 403
    assert response.json()["errors"][0]["message"] == "Restricted namespace 'Internal' used on 'Timestamp'"


async def test_schema_load_endpoint_idempotent_simple(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers,
    default_branch: Branch,
    register_core_schema_db,
    authentication_base,
    helper,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        creation = client.post(
            "/api/schema/load", headers=admin_headers, json={"schemas": [helper.schema_file("infra_simple_01.json")]}
        )
        read = client.get("/api/schema", headers=admin_headers)

        nbr_rels = await count_relationships(db=db)

        assert creation.status_code == 202
        assert read.status_code == 200
        nodes = read.json()["nodes"]
        device = [node for node in nodes if node["name"] == "Device"]
        assert device
        device = device[0]
        attributes = {attrib["name"]: attrib["order_weight"] for attrib in device["attributes"]}
        relationships = {attrib["name"]: attrib["order_weight"] for attrib in device["relationships"]}
        assert attributes["name"] == 1000
        assert attributes["description"] == 900
        assert attributes["type"] == 3000
        assert relationships["interfaces"] == 450
        assert relationships["tags"] == 7000

        creation = client.post(
            "/api/schema/load", headers=admin_headers, json={"schemas": [helper.schema_file("infra_simple_01.json")]}
        )
        read = client.get("/api/schema", headers=admin_headers)

        assert creation.status_code == 202
        assert read.status_code == 200

        assert nbr_rels == await count_relationships(db=db)


async def test_schema_load_endpoint_valid_with_generics(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers,
    default_branch: Branch,
    authentication_base,
    helper,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response1 = client.post(
            "/api/schema/load",
            headers=admin_headers,
            json={"schemas": [helper.schema_file("infra_w_generics_01.json")]},
        )
        assert response1.status_code == 202

        response2 = client.get("/api/schema", headers=admin_headers)
        assert response2.status_code == 200

    schema = response2.json()
    assert len(schema["generics"]) == len(core_models.get("generics")) + 1


async def test_schema_load_endpoint_idempotent_with_generics(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers,
    default_branch: Branch,
    authentication_base,
    helper,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response1 = client.post(
            "/api/schema/load",
            headers=admin_headers,
            json={"schemas": [helper.schema_file("infra_w_generics_01.json")]},
        )
        assert response1.json() == {}
        assert response1.status_code == 202

        response2 = client.get("/api/schema", headers=admin_headers)
        assert response2.status_code == 200

        schema = response2.json()
        assert len(schema["generics"]) == len(core_models.get("generics")) + 1

        nbr_rels = await count_relationships(db=db)

        response3 = client.post(
            "/api/schema/load",
            headers=admin_headers,
            json={"schemas": [helper.schema_file("infra_w_generics_01.json")]},
        )
        assert response3.json() == {}
        assert response3.status_code == 202

        response4 = client.get("/api/schema", headers=admin_headers)
        assert response4.status_code == 200

        nbr_rels_after = await count_relationships(db=db)
        assert nbr_rels == nbr_rels_after


async def test_schema_load_endpoint_valid_with_extensions(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers,
    default_branch: Branch,
    authentication_base,
    helper,
):
    org_schema = registry.schema.get(name="CoreOrganization", branch=default_branch.name)
    initial_nbr_relationships = len(org_schema.relationships)

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post(
            "/api/schema/load",
            headers=admin_headers,
            json={"schemas": [helper.schema_file("infra_w_extensions_01.json")]},
        )

    assert response.status_code == 202

    org_schema = registry.schema.get(name="CoreOrganization", branch=default_branch.name)
    assert len(org_schema.relationships) == initial_nbr_relationships + 1


async def test_schema_load_endpoint_not_valid_simple_02(
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
            json={"schemas": [helper.schema_file("not_valid_simple_02.json")]},
        )

    assert response.status_code == 422


async def test_schema_load_endpoint_not_valid_simple_03(
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
            json={"schemas": [helper.schema_file("not_valid_simple_03.json")]},
        )

    assert response.status_code == 422


async def test_schema_load_endpoint_not_valid_simple_04(
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
            json={"schemas": [helper.schema_file("not_valid_simple_04.json")]},
        )

    assert response.status_code == 422


async def test_schema_load_endpoint_not_valid_simple_05(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers,
    default_branch: Branch,
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
