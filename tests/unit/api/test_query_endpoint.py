import pytest
from fastapi.testclient import TestClient

from infrahub.core.node import Node
from infrahub.main import app


@pytest.fixture
def client():
    return TestClient(app)


headers = {"Authorization": "Token XXXX"}


def test_query_endpoint(default_branch, car_person_schema, client):

    p1 = Node("Person").new(name="John", height=180).save()
    p2 = Node("Person").new(name="Jane", height=170).save()
    Node("Car").new(name="volt", nbr_seats=4, is_electric=True, owner=p1).save()
    Node("Car").new(name="bolt", nbr_seats=4, is_electric=True, owner=p1).save()
    Node("Car").new(name="nolt", nbr_seats=4, is_electric=True, owner=p2).save()

    query = """
    query {
        person {
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

    response = client.post(
        "/graphql",
        json={"query": query},
        headers=headers,
    )
    assert response.status_code == 200
    assert "errors" not in response.json()
    assert response.json()["data"] is not None
    result = response.json()["data"]

    valid_names = ["John", "Jane"]

    assert result["person"][0]["name"]["value"] in valid_names
    assert len(result["person"][0]["cars"]) == 2

    valid_names.remove(result["person"][0]["name"]["value"])
    assert len(valid_names) == 1
    assert result["person"][1]["name"]["value"] in valid_names
    assert len(result["person"][1]["cars"]) == 1
