import graphene
import pytest
from graphql import graphql

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.graphql import get_gql_mutation, get_gql_query


@pytest.mark.asyncio
async def test_delete_object(default_branch, car_person_schema):

    obj1 = Node("Person").new(name="John", height=180).save()
    Node("Person").new(name="Jim", height=160).save()
    Node("Person").new(name="Joe", height=170).save()

    query = (
        """
    mutation {
        person_delete(data: {id: "%s"}) {
            ok
        }
    }
    """
        % obj1.id
    )
    result = await graphql(
        graphene.Schema(query=get_gql_query(), mutation=get_gql_mutation(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_delete"]["ok"] is True

    assert not NodeManager.get_one(obj1.id)
