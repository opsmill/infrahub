from infrahub.auth import AccountSession
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.services import InfrahubServices
from tests.helpers.graphql import graphql_mutation, graphql_query
from tests.helpers.test_app import TestInfrahubApp


class TestNumberSupportsLargeInter(TestInfrahubApp):
    async def test_number_supports_large_integers(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
        register_core_models_schema: SchemaBranch,
        session_admin: AccountSession,
        person_john_main: Node,
        service: InfrahubServices,
    ) -> None:
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

        result = await graphql_mutation(
            query=query, db=db, branch=default_branch, account_session=session_admin, service=service
        )

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

        result = await graphql_query(
            query=query, db=db, branch=default_branch, variables={"ids_test_cars": [id_test_car]}
        )
        assert result.errors is None
        assert result.data
        assert result.data["TestCar"]["edges"][0]["node"]["nbr_seats"]["value"] == 9999999999999
