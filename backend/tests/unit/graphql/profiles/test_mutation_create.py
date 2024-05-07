from graphql import graphql

from infrahub.core.manager import NodeManager
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params


async def test_create_profile(db: InfrahubDatabase, default_branch, car_person_schema):
    query = """
    mutation {
        ProfileTestPersonCreate(data: {
            profile_name: { value: "profile1" },
            profile_priority: { value: 1000 },
            height: { value: 182 },
        }) {
            ok
            object {
                id
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["ProfileTestPersonCreate"]["ok"] is True

    person_id = result.data["ProfileTestPersonCreate"]["object"]["id"]
    assert len(person_id) == 36  # length of an UUID

    profile = await NodeManager.get_one(db=db, id=person_id)
    assert profile.height.value == 182
