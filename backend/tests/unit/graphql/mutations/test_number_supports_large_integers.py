from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from tests.helpers.graphql import graphql_mutation, graphql_query


async def test_number_supports_large_integers(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema,
    register_core_models_schema,
    session_admin,
    person_john_main,
):
    query = """
    mutation {
        TestCarCreate(data: {
                name: { value: "JetTricycle"},
                nbr_seats: { value: 9999999999999 },
                is_electric: { value: false },
                owner: { id: "John" }
            }) {
            ok
            object {
                id
                nbr_seats { value }
            }
        }
    }
    """

    result = await graphql_mutation(query=query, db=db, branch=default_branch, account_session=session_admin)

    assert result.errors is None
    assert result.data
    assert result.data["TestCarCreate"]["ok"] is True
    assert result.data["TestCarCreate"]["object"]["nbr_seats"]["value"] == 9999999999999

    id_test_car = result.data["TestCarCreate"]["object"]["id"]

    query = """
    query (
        $ids_test_cars: [ID]!
    ) {
      TestCar (ids : $ids_test_cars) {
        edges {
          node {
            id
            nbr_seats { value }
          }
        }
      }
    }
    """

    result = await graphql_query(query=query, db=db, branch=default_branch, variables={"ids_test_cars": [id_test_car]})
    assert result.errors is None
    assert result.data
    assert result.data["TestCar"]["edges"][0]["node"]["nbr_seats"]["value"] == 9999999999999
