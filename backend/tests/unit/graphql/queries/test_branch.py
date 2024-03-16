import operator

from graphql import graphql

from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params


async def test_branch_query(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, session_admin):
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
    gql_params = prepare_graphql_params(
        db=db, include_subscription=False, branch=default_branch, account_session=session_admin
    )
    branch3_result = await graphql(
        schema=gql_params.schema,
        source=create_branch_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert branch3_result.errors is None
    assert branch3_result.data
    branch3 = branch3_result.data["BranchCreate"]["object"]

    # Query all branches
    query = """
    query {
        Branch {
            name
            origin_branch
            description
            is_default
            sync_with_git
            is_isolated
            has_schema_changes
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
    assert all_branches.errors is None
    assert all_branches.data
    assert len(all_branches.data["Branch"]) == 2

    expected_branches = [
        {
            "description": "Default Branch",
            "has_schema_changes": False,
            "sync_with_git": True,
            "is_default": True,
            "is_isolated": False,
            "name": "main",
            "origin_branch": "main",
        },
        {
            "description": "my description",
            "has_schema_changes": False,
            "sync_with_git": True,
            "is_default": False,
            "is_isolated": False,
            "name": "branch3",
            "origin_branch": "main",
        },
    ]
    assert all_branches.data["Branch"].sort(key=operator.itemgetter("name")) == expected_branches.sort(
        key=operator.itemgetter("name")
    )

    # Query Branch3 by Name
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
    assert name_response.errors is None
    assert name_response.data
    assert len(name_response.data["Branch"]) == 1
    assert name_response.data["Branch"][0]["name"] == "branch3"

    # Query Branch3 by ID
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

    assert id_response.data
    assert id_response.data["Branch"][0]["name"] == "branch3"
    assert len(id_response.data["Branch"]) == 1
