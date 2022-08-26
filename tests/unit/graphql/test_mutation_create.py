import graphene
import pytest
from graphql import graphql

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.graphql import get_gql_mutation, get_gql_query


@pytest.mark.asyncio
async def test_create_simple_object(default_branch, car_person_schema):

    query = """
    mutation {
        person_create(data: {name: { value: "John"}, height: {value: 182}}) {
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
    assert result.data["person_create"]["ok"] is True
    assert len(result.data["person_create"]["object"]["id"]) == 36  # lenght of an UUID


@pytest.mark.asyncio
async def test_create_object_with_rels(default_branch, car_person_schema):

    Node("Person").new(name="John", height=180).save()

    query = """
    mutation {
        car_create(data: {
            name: { value: "Accord" },
            nbr_seats: { value: 5 },
            is_electric: { value: false },
            owner: "John"
        }) {
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
    assert result.data["car_create"]["ok"] is True
    assert len(result.data["car_create"]["object"]["id"]) == 36  # lenght of an UUID


@pytest.mark.asyncio
async def test_create_person_not_valid(default_branch, car_person_schema):

    query = """
    mutation {
        person_create(data: {name: { value: "John"}, height: {value: "182"}}) {
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

    assert len(result.errors) == 1
    assert "Int cannot represent non-integer value" in result.errors[0].message
