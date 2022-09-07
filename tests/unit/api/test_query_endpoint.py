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

    result_per_name = {result["name"]["value"]: result for result in result["person"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["cars"]) == 2
    assert len(result_per_name["Jane"]["cars"]) == 1
