import graphene
import pytest
from graphql import graphql

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.graphql import get_gql_mutation, get_gql_query


@pytest.mark.asyncio
async def test_update_simple_object(default_branch, car_person_schema):

    obj = Node("Person").new(name="John", height=180).save()

    query = (
        """
    mutation {
        person_update(data: {id: "%s", name: { value: "Jim"}}) {
            ok
            object {
                id
                name {
                    value
                }
            }
        }
    }
    """
        % obj.id
    )
    result = await graphql(
        graphene.Schema(query=get_gql_query(), mutation=get_gql_mutation(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True

    obj1 = NodeManager.get_one(obj.id)
    assert obj1.name.value == "Jim"
    assert obj1.height.value == 180


@pytest.mark.asyncio
async def test_update_object_with_flags(default_branch, car_person_schema):

    obj = Node("Person").new(name="John", height=180).save()

    query = (
        """
    mutation {
        person_update(data: {id: "%s", name: { is_protected: true }, height: { is_visible: false}}) {
            ok
            object {
                id
                name {
                    is_protected
                }
                height {
                    is_visible
                }
            }
        }
    }
    """
        % obj.id
    )
    result = await graphql(
        graphene.Schema(query=get_gql_query(), mutation=get_gql_mutation(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True

    obj1 = NodeManager.get_one(obj.id)
    assert obj1.name.is_protected == True
    assert obj1.height.value == 180
    assert obj1.height.is_visible == False


@pytest.mark.asyncio
async def test_update_object_with_source(default_branch, car_person_schema, first_account, second_account):

    obj = Node("Person").new(name="John", height=180, _source=first_account).save()

    query = """
    mutation {
        person_update(data: {id: "%s", name: { source: "%s" } }) {
            ok
            object {
                id
            }
        }
    }
    """ % (
        obj.id,
        second_account.id,
    )
    result = await graphql(
        graphene.Schema(query=get_gql_query(), mutation=get_gql_mutation(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True

    obj1 = NodeManager.get_one(obj.id, include_source=True)
    assert obj1.name.source_id == second_account.id
    assert obj1.height.source_id == first_account.id


@pytest.mark.asyncio
async def test_update_invalid_object(default_branch, car_person_schema):

    query = """
    mutation {
        person_update(data: {id: "XXXXXX", name: { value: "Jim"}}) {
            ok
            object {
                id
                name {
                    value
                }
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
    assert "Unable to find the node in the database." in result.errors[0].message


@pytest.mark.asyncio
async def test_update_invalid_input(default_branch, car_person_schema):

    obj = Node("Person").new(name="John", height=180).save()

    query = (
        """
    mutation {
        person_update(data: {id: "%s", name: { value: False }}) {
            ok
            object {
                id
                name {
                    value
                }
            }
        }
    }
    """
        % obj.id
    )
    result = await graphql(
        graphene.Schema(query=get_gql_query(), mutation=get_gql_mutation(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert len(result.errors) == 1
    assert "String cannot represent a non string value" in result.errors[0].message


@pytest.mark.asyncio
async def test_update_relationship_many(default_branch, person_tag_schema):

    t1 = Node("Tag").new(name="Blue", description="The Blue tag").save()
    Node("Tag").new(name="Red").save()
    p1 = Node("Person").new(firstname="John", lastname="Doe").save()

    query = """
    mutation {
        person_update(data: {id: "%s", tags: [ "%s" ] }) {
            ok
            object {
                id
                tags {
                    name {
                        value
                    }
                }
            }
        }
    }
    """ % (
        p1.id,
        t1.id,
    )
    result = await graphql(
        graphene.Schema(query=get_gql_query(), mutation=get_gql_mutation(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True
    assert len(result.data["person_update"]["object"]["tags"]) == 1
