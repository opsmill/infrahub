from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from tests.helpers.graphql import graphql


async def test_create_profile(db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch) -> None:
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
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    # gql mutation needs function workflow
    gql_params.context.service = await InfrahubServices.new(workflow=WorkflowLocalExecution())
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
