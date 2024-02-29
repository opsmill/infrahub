from graphql import graphql

from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params


async def test_branch_query(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema, register_core_models_schema
):
    create_branch_query = """
    mutation {
        BranchCreate(data: { name: "branch3", description: "my description" }) {
            ok
            object {
                id
                name
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    branch3_result = await graphql(
        schema=gql_params.schema,
        source=create_branch_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert branch3_result.data
    branch3 = branch3_result.data["BranchCreate"]["object"]
    query = """
    query {
        Branch {
            id
            name
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    all_branches = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    name_query = """
    query {
        Branch(name: "%s" ) {
            id
            name
        }
    }
    """ % branch3["name"]
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    name_response = await graphql(
        schema=gql_params.schema,
        source=name_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    id_query = """
    query {
        Branch(ids: %s ) {
            id
            name
        }
    }
    """ % [branch3["id"]]
    id_query = id_query.replace("'", '"')

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    id_response = await graphql(
        schema=gql_params.schema,
        source=id_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert all_branches.data
    assert name_response.data
    assert id_response.data
    assert len(all_branches.data["Branch"]) == 2
    assert len(name_response.data["Branch"]) == 1
    assert len(id_response.data["Branch"]) == 1
    assert name_response.data["Branch"][0]["name"] == "branch3"
    assert id_response.data["Branch"][0]["name"] == "branch3"
