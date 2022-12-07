import pytest
from fastapi.testclient import TestClient

from infrahub.core.node import Node
from infrahub.main import app


@pytest.fixture
def client():
    return TestClient(app)


headers = {"Authorization": "Token XXXX"}


@pytest.mark.asyncio
async def test_query_endpoint(session, default_branch, car_person_schema):

    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)
    p2 = await Node.init(session=session, schema="Person")
    await p2.new(session=session, name="Jane", height=170)
    await p2.save(session=session)
    c1 = await Node.init(session=session, schema="Car")
    await c1.new(session=session, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(session=session)
    c2 = await Node.init(session=session, schema="Car")
    await c2.new(session=session, name="bolt", nbr_seats=4, is_electric=True, owner=p1)
    await c2.save(session=session)
    c3 = await Node.init(session=session, schema="Car")
    await c3.new(session=session, name="nolt", nbr_seats=4, is_electric=True, owner=p2)
    await c3.save(session=session)

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

    # Must execute in a with block to execute the startup/shutdown events
    with TestClient(app) as client:
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
