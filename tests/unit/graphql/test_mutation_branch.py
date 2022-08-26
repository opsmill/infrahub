import graphene
import pytest
from graphql import graphql

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.graphql import get_gql_mutation, get_gql_query


@pytest.mark.asyncio
async def test_branch_create(default_branch, car_person_schema):

    query = """
    mutation {
        branch_create(data: { name: "branch2", is_data_only: true }) {
            ok
            object {
                id
                name
            }
        }
    }
    """
    result = await graphql(
        graphene.Schema(query=get_gql_query(), mutation=get_gql_mutation(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["branch_create"]["ok"] is True
    assert len(result.data["branch_create"]["object"]["id"]) == 36  # lenght of an UUID

    assert Branch.get_by_name("branch2")

    # Validate that we can't create a branch with a name that already exist
    result = await graphql(
        graphene.Schema(query=get_gql_query(), mutation=get_gql_mutation(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )
    assert len(result.errors) == 1
    assert "The branch branch2, already exist" in result.errors[0].message


@pytest.mark.asyncio
async def test_branch_rebase(default_branch, car_person_schema):

    branch2 = create_branch("branch2")

    query = """
    mutation {
        branch_rebase(data: { name: "branch2" }) {
            ok
            object {
                id
            }
        }
    }
    """
    result = await graphql(
        graphene.Schema(query=get_gql_query(), mutation=get_gql_mutation(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["branch_rebase"]["ok"] is True
    assert result.data["branch_rebase"]["object"]["id"] == branch2.uuid

    new_branch2 = Branch.get_by_name("branch2")
    assert new_branch2.branched_from != branch2.branched_from


@pytest.mark.asyncio
async def test_branch_validate(default_branch, register_core_models_schema):

    # Not much to validate on this one yet ...
    branch2 = create_branch("branch2")

    query = """
    mutation {
        branch_validate(data: { name: "branch2" }) {
            ok
            object {
                id
            }
        }
    }
    """
    result = await graphql(
        graphene.Schema(query=get_gql_query(), mutation=get_gql_mutation(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["branch_validate"]["ok"] is True
    assert result.data["branch_validate"]["object"]["id"] == branch2.uuid


@pytest.mark.asyncio
async def test_branch_merge(default_branch, register_core_models_schema):

    # Not much to validate on this one yet ...
    branch2 = create_branch("branch2")

    query = """
    mutation {
        branch_merge(data: { name: "branch2" }) {
            ok
            object {
                id
            }
        }
    }
    """
    result = await graphql(
        graphene.Schema(query=get_gql_query(), mutation=get_gql_mutation(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["branch_merge"]["ok"] is True
    assert result.data["branch_merge"]["object"]["id"] == branch2.uuid
