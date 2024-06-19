from graphql import graphql

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params

SEARCH_QUERY = """
query ($search: String!) {
    SearchAnywhere(q: $search) {
        count
        edges {
            node {
                id
                __typename
            }
        }
    }
}
"""


async def test_search_anywhere_by_uuid(
    db: InfrahubDatabase,
    car_accord_main: Node,
    car_camry_main: Node,
    car_volt_main: Node,
    car_prius_main: Node,
    car_yaris_main: Node,
    branch: Branch,
):
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch)

    result = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": car_accord_main.id},
    )

    assert result.errors is None
    assert result.data
    assert result.data["SearchAnywhere"]["count"] == 1
    assert result.data["SearchAnywhere"]["edges"][0]["node"]["id"] == car_accord_main.id
    assert result.data["SearchAnywhere"]["edges"][0]["node"]["__typename"] == car_accord_main.get_kind()


async def test_search_anywhere_by_string(
    db: InfrahubDatabase,
    person_john_main: Node,
    person_jane_main: Node,
    car_accord_main: Node,
    car_camry_main: Node,
    car_volt_main: Node,
    car_prius_main: Node,
    car_yaris_main: Node,
    branch: Branch,
):
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch)

    result = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "prius"},
    )

    assert result.errors is None
    assert result.data
    assert result.data["SearchAnywhere"]["count"] == 1
    assert result.data["SearchAnywhere"]["edges"][0]["node"]["id"] == car_prius_main.id
    assert result.data["SearchAnywhere"]["edges"][0]["node"]["__typename"] == car_prius_main.get_kind()

    result = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "j"},
    )

    assert result.errors is None
    assert result.data
    assert result.data["SearchAnywhere"]["count"] == 2
    assert result.data["SearchAnywhere"]["count"] == 1
    assert result.data["SearchAnywhere"]["edges"][0]["node"]["id"] == person_john_main.id
    assert result.data["SearchAnywhere"]["edges"][0]["node"]["__typename"] == person_john_main.get_kind()
    assert result.data["SearchAnywhere"]["edges"][1]["node"]["id"] == person_jane_main.id
    assert result.data["SearchAnywhere"]["edges"][1]["node"]["__typename"] == person_jane_main.get_kind()
