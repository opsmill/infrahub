from uuid import uuid4

from graphql import graphql

from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params

CREATE_PROPOSED_CHANGE = """
mutation ProposedChange(
  $destination: String!,
  $name: String!,
  $source: String!
  ) {
  CoreProposedChangeCreate(
    data: {
      name: {value: $name},
      source_branch: {value: $source},
      destination_branch: {value: $destination}
    }
  ) {
    ok
    object {
      id
    }
  }
}
"""


async def test_create_invalid_branch_combinations(db: InfrahubDatabase, default_branch, register_core_models_schema):
    branch_name = str(uuid4().hex)
    invalid_branch = str(uuid4().hex)
    source_branch = Branch(name=branch_name)
    await source_branch.save(db=db)

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    no_source = await graphql(
        schema=gql_params.schema,
        source=CREATE_PROPOSED_CHANGE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"source": invalid_branch, "destination": "main", "name": "invalid-source"},
    )

    invalid_combination = await graphql(
        schema=gql_params.schema,
        source=CREATE_PROPOSED_CHANGE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "source": source_branch.name,
            "destination": source_branch.name,
            "name": "invalid-combination",
        },
    )

    invalid_destination = await graphql(
        schema=gql_params.schema,
        source=CREATE_PROPOSED_CHANGE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "source": source_branch.name,
            "destination": "not-main",
            "name": "invalid-destination",
        },
    )

    assert no_source.errors
    assert "The specified source branch for this proposed change was not found" in str(no_source.errors)

    assert invalid_combination.errors
    assert "The source and destination branch can't be the same" in str(invalid_combination.errors)

    assert invalid_destination.errors
    assert "Currently only the 'main' branch is supported as a destination for a proposed change" in str(
        invalid_destination.errors
    )
