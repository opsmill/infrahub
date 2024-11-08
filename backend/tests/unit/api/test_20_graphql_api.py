import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


async def test_graphql_endpoint(
    db: InfrahubDatabase, client, admin_headers, default_branch: Branch, create_test_admin, car_person_data
):
    query = """
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

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post("/graphql", json={"query": query}, headers=admin_headers)

    assert response.status_code == 200
    assert "errors" not in response.json()
    assert response.json()["data"] is not None
    result = response.json()["data"]

    result_per_name = {result["node"]["name"]["value"]: result for result in result["TestPerson"]["edges"]}

    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["node"]["cars"]["edges"]) == 2
    assert len(result_per_name["Jane"]["node"]["cars"]["edges"]) == 1


async def test_graphql_endpoint_with_timestamp(
    db: InfrahubDatabase, client, admin_headers, default_branch: Branch, create_test_admin, car_person_data
):
    time_before = Timestamp()

    p1 = car_person_data["p1"]
    p1.name.value = "Johnny"
    await p1.save(db=db)

    query = """
    query {
        TestPerson {
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

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post("/graphql", json={"query": query}, headers=admin_headers)

    assert response.status_code == 200
    assert "errors" not in response.json()
    assert response.json()["data"] is not None
    result = response.json()["data"]

    names = [result["node"]["name"]["value"] for result in result["TestPerson"]["edges"]]

    assert sorted(names) == ["Jane", "Johnny"]

    with client:
        response = client.post(f"/graphql?at={time_before.to_string()}", json={"query": query}, headers=admin_headers)

    assert response.status_code == 200
    assert "errors" not in response.json()
    assert response.json()["data"] is not None
    result = response.json()["data"]

    names = [result["node"]["name"]["value"] for result in result["TestPerson"]["edges"]]

    assert sorted(names) == ["Jane", "John"]


@pytest.mark.xfail(reason="Need to investigate, Currently working alone but failing when it's part of the test suite")
async def test_graphql_endpoint_generics(
    db: InfrahubDatabase, default_branch: Branch, client, client_headers, car_person_data_generic
):
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

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post(
            "/graphql",
            json={"query": query},
            headers=client_headers,
        )

    assert response.status_code == 200
    assert "errors" not in response.json()
    assert response.json()["data"] is not None
    result = response.json()["data"]

    result_per_name = {result["name"]["value"]: result for result in result["TestPerson"]}

    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["cars"]) == 2
    assert len(result_per_name["Jane"]["cars"]) == 1


async def test_graphql_options(db: InfrahubDatabase, client, client_headers, default_branch: Branch, car_person_data):
    await create_branch(branch_name="branch2", db=db)

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.options(
            "/graphql",
            headers=client_headers,
        )

        assert response.status_code == 200
        assert "Allow" in response.headers
        assert response.headers["Allow"] == "GET, POST, OPTIONS"

        response = client.options(
            "/graphql/branch2",
            headers=client_headers,
        )

        assert response.status_code == 200
        assert "Allow" in response.headers
        assert response.headers["Allow"] == "GET, POST, OPTIONS"

        response = client.options(
            "/graphql/notvalid",
            headers=client_headers,
        )

        assert response.status_code == 404


async def test_read_profile(
    db: InfrahubDatabase,
    client,
    admin_headers,
    authentication_base,
):
    query = """
    query {
        AccountProfile {
            name {
                value
            }
        }
    }
    """

    with client:
        response = client.post(
            "/graphql",
            json={"query": query},
            headers=admin_headers,
        )

    assert response.status_code
    assert response.json() == {"data": {"AccountProfile": {"name": {"value": "test-admin"}}}}


async def test_download_schema(db: InfrahubDatabase, client, client_headers):
    await create_branch(branch_name="branch2", db=db)

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get("/schema.graphql", headers=client_headers)
        assert response.status_code == 200

        response = client.get("/schema.graphql?branch=branch2", headers=client_headers)
        assert response.status_code == 200

        response = client.get("/schema.graphql?branch=notvalid", headers=client_headers)
        assert response.status_code == 400


async def test_query_at_previous_schema(
    db: InfrahubDatabase,
    client,
    admin_headers,
    default_branch: Branch,
    authentication_base,
    prefect_test_fixture,
    workflow_local,
    car_person_data,
):
    # Load the schema in the database
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    await registry.schema.load_schema_to_db(schema=schema, branch=default_branch, db=db)

    time_before = Timestamp()

    query = """
    query {
        TestPerson {
            edges {
                node {
                    display_label
                }
            }
        }
    }
    """

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post(
            "/graphql",
            json={"query": query},
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]
        assert result == {
            "TestPerson": {
                "edges": [
                    {"node": {"display_label": "John"}},
                    {"node": {"display_label": "Jane"}},
                ],
            },
        }

        creation = client.post(
            "/api/schema/load",
            headers=admin_headers,
            json={
                "schemas": [
                    {
                        "version": "1.0",
                        "nodes": [
                            {
                                "name": "Person",
                                "namespace": "Test",
                                "default_filter": "name__value",
                                "display_labels": ["name__value", "height__value"],
                                "attributes": [
                                    {"name": "name", "kind": "Text", "unique": True},
                                    {"name": "height", "kind": "Number", "optional": True},
                                ],
                                "relationships": [
                                    {"name": "cars", "peer": "TestCar", "cardinality": "many", "direction": "inbound"}
                                ],
                            },
                        ],
                    }
                ]
            },
        )
        data = creation.json()
        assert data
        assert data.get("schema_updated") is True
        assert "diff" in data
        assert data["diff"] == {
            "added": {},
            "changed": {
                "TestPerson": {"added": {}, "changed": {"display_labels": None}, "removed": {}},
            },
            "removed": {},
        }
        assert creation.status_code == 200

        # Do another query to validate that the schema has been updated
        response = client.post(
            "/graphql",
            json={"query": query},
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]
        assert result == {
            "TestPerson": {
                "edges": [
                    {"node": {"display_label": "John 180"}},
                    {"node": {"display_label": "Jane 170"}},
                ],
            },
        }

        # Query before we updated the schema to validate that we can pull the latest schema
        response = client.post(
            f"/graphql?at={time_before.to_string()}",
            json={"query": query},
            headers=admin_headers,
        )

        assert "errors" not in response.json()
        assert response.status_code == 200
        assert response.json()["data"] is not None
        result = response.json()["data"]
        assert result == {
            "TestPerson": {
                "edges": [
                    {"node": {"display_label": "John"}},
                    {"node": {"display_label": "Jane"}},
                ],
            },
        }
