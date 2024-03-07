from graphql import graphql

from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params


async def test_relationship(
    db: InfrahubDatabase,
    person_john_main,
    person_jane_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
):
    query = """
    query (
        $relationship_identifiers: [String!]!
    ) {
        Relationship(ids: $relationship_identifiers) {
            count
            edges {
                node {
                    identifier
                    peers {
                        id
                        kind
                    }
                }
            }
        }
    }
    """

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch)

    # No identifiers
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"relationship_identifiers": []},
    )

    assert result.errors is not None
    assert len(result.errors) == 1

    # One identifier
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"relationship_identifiers": ["testcar__testperson"]},
    )

    assert result.errors is None
    assert result.data
    assert result.data["Relationship"]["count"] == 5
